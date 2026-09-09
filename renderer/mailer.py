"""Sign-up verification by emailed code.

Nobody gets an account without proving they hold the address, which matters
because the address is what grants access to every client proposal.
"""
import os
import re
import smtplib
import ssl
import unicodedata
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formataddr, make_msgid


def _clean(value):
    """Values pasted from a browser often carry non-breaking spaces and other
    invisible characters. One of those in a header stops the send."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    return text.strip()

HOST = _clean(os.environ.get("SMTP_HOST", ""))
PORT = int(_clean(os.environ.get("SMTP_PORT", "587")) or 587)
USER = _clean(os.environ.get("SMTP_USER", ""))
# Google shows an app password as four blocks of four. Those spaces are for
# reading, and pasting them, especially as non-breaking spaces, breaks the login.
PASSWORD = re.sub(r"\s+", "",
                  unicodedata.normalize("NFKC",
                                        os.environ.get("SMTP_PASSWORD", "")))
SENDER = _clean(os.environ.get("SMTP_FROM", "")) or USER or \
    "no-reply@inceptivesdigital.com"
SENDER_NAME = _clean(os.environ.get("SMTP_FROM_NAME",
                                    "Inceptives Digital Proposal Studio"))
# with no mail server configured the code is printed to the server log, which is
# fine on your own machine and refused in production
DEV_ECHO = os.environ.get("OTP_DEV_ECHO", "1") == "1"


def configured():
    return bool(HOST and USER and PASSWORD)


def _non_ascii(label, raw):
    """Name the setting and the position, so nobody has to guess again."""
    out = []
    for i, ch in enumerate(raw or ""):
        if ord(ch) > 127:
            out.append("%s contains %s at position %d"
                       % (label, unicodedata.name(ch, repr(ch)), i))
    return out


def contracts_from_ok():
    """Is the contracts address one this server can actually send as?"""
    if not CONTRACTS_FROM or not USER:
        return True
    return CONTRACTS_FROM.lower() == USER.lower() or \
        CONTRACTS_FROM.rsplit("@", 1)[-1].lower() == USER.rsplit("@", 1)[-1].lower()


def check():
    """What is configured, and whether anything looks wrong with it."""
    problems = []
    if not contracts_from_ok():
        problems.append(
            "CONTRACTS_FROM (%s) is not on the same domain as SMTP_USER (%s). "
            "Mail sent as that address will usually be treated as spam."
            % (CONTRACTS_FROM, USER))
    for label, value in (("SMTP_HOST", HOST), ("SMTP_USER", USER),
                         ("SMTP_PASSWORD", PASSWORD)):
        if not value:
            problems.append("%s is not set" % label)
    if SENDER and "@" not in SENDER:
        problems.append("SMTP_FROM is not an email address")
    # check the raw values, before cleaning, so the source of a bad character
    # is visible even though the code now copes with it
    for label in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM",
                  "SMTP_FROM_NAME"):
        problems += _non_ascii(label, os.environ.get(label, ""))
    if PASSWORD and len(PASSWORD) != 16:
        problems.append("SMTP_PASSWORD is %d characters. A Google app password "
                        "is 16 with no spaces." % len(PASSWORD))
    return {"configured": configured(), "host": HOST, "port": PORT,
            "sender": SENDER, "sender_name": SENDER_NAME,
            "contracts_from": CONTRACTS_FROM,
            "password_length": len(PASSWORD), "problems": problems}


def send_code(to_email, code, purpose="verify your email"):
    subject = "%s is your verification code" % code
    body = (
        "Someone asked to %s for the Inceptives Digital Proposal Studio.\n\n"
        "    %s\n\n"
        "The code expires in 10 minutes. If this was not you, ignore this "
        "message and the account will not be created.\n" % (purpose, code))
    if not configured():
        if DEV_ECHO:
            print("\n  [no mail server configured] verification code for %s: %s\n"
                  % (to_email, code))
            return {"sent": False, "echoed": True}
        raise RuntimeError(
            "Email is not configured, so verification codes cannot be sent. "
            "Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD.")
    msg = EmailMessage()
    msg["Subject"] = subject
    # formataddr encodes a non-ASCII display name properly instead of failing
    msg["From"] = formataddr((SENDER_NAME, SENDER))
    msg["To"] = _clean(to_email)
    msg["Message-ID"] = make_msgid(domain=SENDER.rsplit("@", 1)[-1])
    msg.set_content(body, charset="utf-8")
    context = ssl.create_default_context()
    try:
        return _deliver(msg, context)
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            "One of the SMTP settings contains a character that cannot be sent "
            "over SMTP, usually a non-breaking space pasted from a browser. "
            "Check /api/health, which now names the setting. (%s)" % exc)
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "The mail server refused the login. For Google Workspace this must "
            "be a 16-character app password, not the account password.")
    except smtplib.SMTPException as exc:
        raise RuntimeError("The mail server rejected the message: %s" % exc)
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            "One of the SMTP settings contains a character that cannot be sent "
            "in an email header, usually a non-breaking space pasted from a "
            "browser. Retype SMTP_FROM_NAME and SMTP_FROM by hand. (%s)" % exc)


def _deliver(msg, context):
    if PORT == 465:
        with smtplib.SMTP_SSL(HOST, PORT, context=context, timeout=25) as s:
            s.login(USER, PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(HOST, PORT, timeout=25) as s:
            s.ehlo()
            s.starttls(context=context)
            s.ehlo()
            s.login(USER, PASSWORD)
            s.send_message(msg)
    return {"sent": True, "echoed": False}


# ---------------------------------------------------------------------------
# Contract emails
# ---------------------------------------------------------------------------
# Sent from the mailbox that is authenticated, but presented as the contracts
# address, so a client sees the address you want them to reply to. Both are on
# your own domain, so this does not break SPF or DKIM.

# Defaults to the authenticated mailbox. Sending as an address the server does
# not own fails SPF and lands in spam, which defeats the point.
CONTRACTS_FROM = _clean(os.environ.get("CONTRACTS_FROM", "")) or USER or SENDER
CONTRACTS_NAME = _clean(os.environ.get("CONTRACTS_FROM_NAME",
                                       "Inceptives Digital"))


def send_contract(to_email, to_name, subject, body_text, link,
                  project="", total="", signer=""):
    """The signing invitation, from your own domain.

    Plain text and HTML, because some clients read one and some the other, and
    a link that only exists in an HTML button is a link half your recipients
    cannot use.
    """
    if not configured():
        raise RuntimeError(
            "Email is not configured, so the invitation cannot be sent from "
            "your own address. Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD, or "
            "send it through the signing service instead.")
    if not link:
        raise RuntimeError("There is no signing link to send yet.")

    msg = EmailMessage()
    msg["Subject"] = _clean(subject)
    msg["From"] = formataddr((CONTRACTS_NAME, CONTRACTS_FROM))
    msg["To"] = formataddr((_clean(to_name), _clean(to_email)))
    msg["Reply-To"] = CONTRACTS_FROM
    msg["Message-ID"] = make_msgid(domain=CONTRACTS_FROM.rsplit("@", 1)[-1])

    msg.set_content(
        "%s\n\nReview and sign here:\n%s\n\n%s\n%s\n"
        % (body_text, link,
           ("Project: %s" % project) if project else "",
           ("Total: %s" % total) if total else ""),
        charset="utf-8")

    rows = ""
    if project:
        rows += _row("Project", project)
    if total:
        rows += _row("Total", total)
    if signer:
        rows += _row("Already signed by", signer)

    msg.add_alternative(_HTML % {
        "body": _escape(body_text).replace("\n", "<br>"),
        "link": link,
        "rows": rows,
        "from": CONTRACTS_FROM,
        "name": CONTRACTS_NAME,
    }, subtype="html")
    return _deliver(msg, ssl.create_default_context())


def _escape(text):
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _row(label, value):
    return ('<tr><td style="padding:7px 0;color:#6b7280;font-size:13px;'
            'width:150px">%s</td><td style="padding:7px 0;font-size:13px;'
            'color:#12151c">%s</td></tr>' % (_escape(label), _escape(value)))


_HTML = """\
<!doctype html><html><body style="margin:0;background:#f4f6fa;padding:26px 12px">
<table role="presentation" width="100%%" cellpadding="0" cellspacing="0">
<tr><td align="center">
<table role="presentation" width="100%%" style="max-width:560px;background:#fff;
  border:1px solid #e7ebf2;border-radius:16px;overflow:hidden">
  <tr><td style="padding:26px 30px 6px">
    <div style="font:600 15px/1.3 -apple-system,'Segoe UI',Roboto,sans-serif;
      color:#4160aa">Inceptives Digital</div>
  </td></tr>
  <tr><td style="padding:8px 30px 0;font:15px/1.6 -apple-system,'Segoe UI',
    Roboto,sans-serif;color:#12151c">%(body)s</td></tr>
  <tr><td style="padding:24px 30px 4px">
    <a href="%(link)s" style="display:inline-block;background:#4160aa;
      color:#ffffff;font:600 15px/1 -apple-system,'Segoe UI',Roboto,sans-serif;
      padding:15px 26px;border-radius:10px;text-decoration:none">
      Review and sign</a>
  </td></tr>
  <tr><td style="padding:6px 30px 0;font:13px/1.5 -apple-system,'Segoe UI',
    Roboto,sans-serif;color:#6b7280">
    Or paste this into your browser:<br>
    <a href="%(link)s" style="color:#4160aa;word-break:break-all">%(link)s</a>
  </td></tr>
  <tr><td style="padding:18px 30px 0">
    <table role="presentation" width="100%%" style="border-top:1px solid #e7ebf2;
      font-family:-apple-system,'Segoe UI',Roboto,sans-serif">%(rows)s</table>
  </td></tr>
  <tr><td style="padding:20px 30px 28px;font:12.5px/1.5 -apple-system,
    'Segoe UI',Roboto,sans-serif;color:#9aa3b2">
    Signed securely through SignWell. If anything needs changing before you
    sign, reply to this email and we will sort it out.<br>
    <span style="color:#c3cad6">%(name)s &middot; %(from)s</span>
  </td></tr>
</table>
</td></tr></table></body></html>
"""

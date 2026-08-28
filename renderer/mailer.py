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


def check():
    """What is configured, and whether anything looks wrong with it."""
    problems = []
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

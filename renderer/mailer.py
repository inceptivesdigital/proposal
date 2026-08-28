"""Sign-up verification by emailed code.

Nobody gets an account without proving they hold the address, which matters
because the address is what grants access to every client proposal.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

HOST = os.environ.get("SMTP_HOST", "")
PORT = int(os.environ.get("SMTP_PORT", "587"))
USER = os.environ.get("SMTP_USER", "")
PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SENDER = os.environ.get("SMTP_FROM", USER or "no-reply@inceptivesdigital.com")
SENDER_NAME = os.environ.get("SMTP_FROM_NAME", "Inceptives Digital Proposal Studio")
# with no mail server configured the code is printed to the server log, which is
# fine on your own machine and refused in production
DEV_ECHO = os.environ.get("OTP_DEV_ECHO", "1") == "1"


def configured():
    return bool(HOST and USER and PASSWORD)


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
    msg["From"] = "%s <%s>" % (SENDER_NAME, SENDER)
    msg["To"] = to_email
    msg.set_content(body)
    context = ssl.create_default_context()
    if PORT == 465:
        with smtplib.SMTP_SSL(HOST, PORT, context=context, timeout=20) as s:
            s.login(USER, PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(HOST, PORT, timeout=20) as s:
            s.starttls(context=context)
            s.login(USER, PASSWORD)
            s.send_message(msg)
    return {"sent": True, "echoed": False}

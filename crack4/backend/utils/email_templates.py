"""Branded email templates for transactional mail."""


def verification_email_html(verify_url: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#0b0b0f;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#fff;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#15151c;border-radius:12px;padding:32px;">
        <tr><td>
          <h1 style="margin:0 0 8px 0;font-size:22px;letter-spacing:2px;color:#ff6a3d;">CRACK</h1>
          <p style="margin:0 0 24px 0;color:#9aa0a6;font-size:13px;">Track It First</p>
          <h2 style="margin:0 0 12px 0;font-size:20px;">Verify your email</h2>
          <p style="margin:0 0 24px 0;font-size:14px;line-height:1.5;color:#cfcfd4;">
            Tap the button below to confirm your email and finish creating your CRACK account. This link expires in 24 hours.
          </p>
          <p style="margin:0 0 24px 0;">
            <a href="{verify_url}" style="display:inline-block;background:#ff6a3d;color:#fff;text-decoration:none;font-weight:700;padding:14px 24px;border-radius:8px;font-size:15px;">Verify email</a>
          </p>
          <p style="margin:0 0 8px 0;font-size:12px;color:#7c8189;">If the button doesn't work, paste this link into your browser:</p>
          <p style="margin:0;font-size:12px;color:#7c8189;word-break:break-all;">{verify_url}</p>
          <hr style="border:none;border-top:1px solid #2a2a33;margin:24px 0;">
          <p style="margin:0;font-size:11px;color:#7c8189;">If you didn't sign up for CRACK, you can safely ignore this email.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def verification_email_text(verify_url: str) -> str:
    return (
        "Welcome to CRACK!\n\n"
        "Verify your email to finish creating your account:\n"
        f"{verify_url}\n\n"
        "This link expires in 24 hours. If you didn't sign up, ignore this email.\n"
    )


def password_reset_email_html(reset_url: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#0b0b0f;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#fff;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#15151c;border-radius:12px;padding:32px;">
        <tr><td>
          <h1 style="margin:0 0 8px 0;font-size:22px;letter-spacing:2px;color:#ff6a3d;">CRACK</h1>
          <p style="margin:0 0 24px 0;color:#9aa0a6;font-size:13px;">Track It First</p>
          <h2 style="margin:0 0 12px 0;font-size:20px;">Reset your password</h2>
          <p style="margin:0 0 24px 0;font-size:14px;line-height:1.5;color:#cfcfd4;">
            We received a request to reset your CRACK account password. Tap the button below to choose a new password. This link expires in 15 minutes.
          </p>
          <p style="margin:0 0 24px 0;">
            <a href="{reset_url}" style="display:inline-block;background:#ff6a3d;color:#fff;text-decoration:none;font-weight:700;padding:14px 24px;border-radius:8px;font-size:15px;">Reset password</a>
          </p>
          <p style="margin:0 0 8px 0;font-size:12px;color:#7c8189;">If the button doesn't work, paste this link into your browser:</p>
          <p style="margin:0;font-size:12px;color:#7c8189;word-break:break-all;">{reset_url}</p>
          <hr style="border:none;border-top:1px solid #2a2a33;margin:24px 0;">
          <p style="margin:0;font-size:11px;color:#7c8189;">If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def password_reset_email_text(reset_url: str) -> str:
    return (
        "CRACK Password Reset\n\n"
        "Tap the link below to choose a new password for your account:\n"
        f"{reset_url}\n\n"
        "This link expires in 15 minutes. If you didn't request this, ignore this email.\n"
    )


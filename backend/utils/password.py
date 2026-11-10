import secrets
import string

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SPECIAL = "!@#$%^&*-_=+.,?~/"
ALL_CHARS = LOWER + UPPER + DIGITS + SPECIAL


def validate_password(password: str, min_length: int = 8) -> dict:
    """Validate that a password meets minimum security strength rules.

    Returns:
        dict: {'is_valid': bool, 'errors': list[str], 'message': str}
    """
    if not isinstance(password, str):
        return {
            "is_valid": False,
            "errors": ["Password must be a string."],
            "message": "Password must be a string.",
        }

    errors = []

    # Rule 1: Minimum length
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters long.")

    # Rule 2: At least one lowercase letter
    if not any(char in LOWER for char in password):
        errors.append("Password must contain at least one lowercase letter.")

    # Rule 3: At least one uppercase letter
    if not any(char in UPPER for char in password):
        errors.append("Password must contain at least one uppercase letter.")

    # Rule 4: At least one digit
    if not any(char in DIGITS for char in password):
        errors.append("Password must contain at least one number.")

    # Rule 5: At least one special symbol
    if not any(char in SPECIAL for char in password):
        errors.append("Password must contain at least one special character (!@#$%^&*-_=+.,?~/).")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "message": " ".join(errors) if errors else "Password is strong.",
    }


def generate_password(length: int = 12) -> str:
    """Generate a cryptographically secure random password meeting all strength rules."""
    if length < 8:
        raise ValueError("Password length must be at least 8 characters.")
 
    # Step 1: Guarantee at least one of each required character type
    password_chars = [
        secrets.choice(LOWER),
        secrets.choice(UPPER),
        secrets.choice(DIGITS),
        secrets.choice(SPECIAL),
    ]

    # Step 2: Fill the remaining length with random characters from all allowed types
    password_chars += [secrets.choice(ALL_CHARS) for _ in range(length - 4)]

    # Step 3: Shuffle so the required characters aren't predictably in the first 4 positions
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)
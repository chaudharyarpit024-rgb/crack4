import secrets
import string

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SPECIAL ="!@#$%^&*-_=+"
ALL_CHARS = LOWER + UPPER + DIGITS + SPECIAL


def validate_password(password: str, min_length: int = 8) -> dict:
    if not isinstance(password, str): 
        return{
            "is_valid": False,
            "errors": ["Password must be a string. "]
        }
    errors = []

    # Rule 1: minimum length
    if len( password ) < min_length:
        errors.append(f"Password must be at least {min_length} characters long.")
    # Rule 2: At least one lowercase letter.
    if not any(char in LOWER for char in password):
        errors.append("Password must contain at least one lowercase letter.")

    if not any(char in UPPER for char in password):
        errors.append("Password must contain at least one uppercase letter.")


    if not any(char in DIGITS for char in password):
        errors.append("Password must contain at least one digit.")

    if not any(char in SPECIAL for char in password):
        errors.append("Password must contain at least one special character.")
    
    return {
        "is_valid": not errors,
        "errors": errors
    }


def generate_password( length: int = 12) -> str: 

        if length < 8: 
            raise ValueError("Password length must be at least 8 characters.")

        # Step 1: Ensuring at least one of each required type.

        password_chars = [
            secrets.choice(LOWER),  
            secrets.choice(UPPER),  
            secrets.choice(DIGITS),  
            secrets.choice(SPECIAL),  
        ]

        # Step 2: Filling the remaining length with random characters from all allowed types.
        
        password_chars += [secrets.choice(ALL_CHARS) for _ in range(length - 4)]

        # Step 3: Shuffle them up so the required characters aren't always at the start.
        secrets.SystemRandom().shuffle(password_chars)

        return "".join(password_chars)
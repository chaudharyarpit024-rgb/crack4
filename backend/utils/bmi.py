from logging import error
from typing import Optional

def calculateBMI(weight_kg: float, height_cm: float) -> dict:
    """
    Calculates the Body Mass Index (BMI) given weight in kilograms and height in centimeters.
    
    Args:
        weight_kg (float): The weight in kilograms.
        height_cm (float): The height in centimeters.
        
    Returns:
        dict: A dictionary containing the calculated BMI.
    """
    
    # Calculate BMI using the formula: weight / ((height / 100) ** 2)
    if not weight_kg or not height_cm or weight_kg <= 0 or height_cm <= 0:
        raise ValueError("Please check values of Weight and Height")
    
    bmi = weight_kg / ((height_cm / 100) ** 2)

    if bmi <= 18.5:
        category = "Under Weight"
    elif bmi <=24.9:
        category = "Normal Weight"
    elif bmi  <= 29.9:
        category = "Over Weight"
    else: 
        category = "Obesity"
    
    return {
        "BMI: ": round(bmi,1),
        "Category: " : category
    }
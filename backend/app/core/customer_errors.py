"""Customer messages are authored here; exception text remains internal."""

MESSAGES = {
    "VALIDATION_ERROR": "Check your transaction details and try again.",
    "QUOTE_CHANGED": "Availability has changed. Review the updated quote before continuing.",
    "QUOTE_EXPIRED": "Your quote has expired. Check availability again.",
    "QUOTE_UNAVAILABLE": "This amount is currently unavailable. Choose another amount.",
    "RATE_EXPIRED": "The exchange rate has expired. Review a new quote.",
    "RATE_UNAVAILABLE": "Exchange rates are temporarily unavailable.",
    "COIN_INTAKE_UNAVAILABLE": "Coin intake is unavailable. Check the accepted cash options.",
    "LOCKED_OUT": "The kiosk is temporarily unavailable. Please ask an operator for assistance.",
    "PAYMENT_GATEWAY_ERROR": "Payment status is being checked. Keep this screen open.",
}


def customer_message(code=None):
    return MESSAGES.get(code, "We could not complete this action. Check the transaction status before trying again.")


def validation_fields(errors):
    messages = {
        "mobile_number": "Enter an 11-digit mobile number starting with 09.",
        "amount": "Enter a valid whole peso amount within the displayed limit.",
        "quote_id": "Check availability again before continuing.",
    }
    return [{"field": field, "message": messages.get(field, MESSAGES["VALIDATION_ERROR"])}
            for error in errors if (field := next((part for part in error.get("loc", ())
                                                   if part in messages), None))]

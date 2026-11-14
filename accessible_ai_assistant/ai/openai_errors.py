from openai import APIStatusError


def credits_exhausted(error: Exception) -> bool:
    return isinstance(error, APIStatusError) and error.code == "credit_balance_exhausted"

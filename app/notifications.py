def notify_error(error: Exception, context: dict) -> None:
    print("AGENT ERROR")
    print("error", str(error))
    print("context", context)

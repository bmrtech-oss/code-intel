def used_function():
    """This function is called by the main entry point."""
    return "I am useful!"

def dead_function():
    """This function is never called and should be flagged as dead code."""
    return "I am lonely..."

if __name__ == "__main__":
    print(used_function())

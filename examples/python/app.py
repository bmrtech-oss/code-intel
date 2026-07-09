def used_function():
    """This function is called by the main entry point."""
    return "I am useful!"

def dead_function():
    """This function is never called and should be flagged as dead code."""
    return "I am lonely..."
    
class Processor:
    def process(self, data):
        # Dynamic call (Confidence 0.3)
        return getattr(self, "_internal")(data)

    def _internal(self, data):
        return data.strip()

def main():
    # Direct call (Confidence 1.0)
    p = Processor()
    
    # Attribute call (Confidence 0.5)
    result = p.process(" hello ")
    print(result)

if __name__ == "__main__":
    print(used_function())
    main()
    

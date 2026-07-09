from app import used_function, dead_function

def test_used_function():
    assert used_function() == "I am useful!"

def test_dead_function():
    # Even though it's dead code in the app, we can still test it.
    assert dead_function() == "I am lonely..."

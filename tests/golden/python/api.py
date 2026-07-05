class APIHandler:
    def __init__(self, repository):
        self.repository = repository

    def handle_request(self, request_data):
        print("Handling request")
        processed_data = self._process(request_data)
        return self.repository.save(processed_data)

    def _process(self, data):
        # Deep call chain
        return self._deep_1(data)

    def _deep_1(self, data):
        return self._deep_2(data)

    def _deep_2(self, data):
        return data.upper()

def dead_function():
    print("I am never called")
    return None

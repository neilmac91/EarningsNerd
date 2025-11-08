class BaseModel:
    def __init__(self, **data):
        for name, value in self.__class__.__dict__.items():
            if name.startswith('__'):
                continue
            if callable(value):
                continue
            if name not in data:
                if isinstance(value, list):
                    setattr(self, name, list(value))
                elif isinstance(value, dict):
                    setattr(self, name, dict(value))
                else:
                    setattr(self, name, value)
        for key, value in data.items():
            setattr(self, key, value)

    def model_dump(self):
        return {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith('_')
        }

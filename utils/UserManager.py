class UserManager:
    INSTANCE = None
    memory = {}

    def __new__(cls, *args, **kwargs):
        if UserManager.INSTANCE is None:
            UserManager.INSTANCE = super().__new__(cls, *args, **kwargs)
        return UserManager.INSTANCE
    
    def get_all_active_users(self):
        yield from UserManager.memory.keys()

    def get(self, key):
        return UserManager.memory.get(key)

    def put(self, key, value):
        UserManager.memory[key] = value
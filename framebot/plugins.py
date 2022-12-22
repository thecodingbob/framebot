class FrameBotPlugin:

    def __has_method(self, method_name: str):
        return callable(getattr(self, method_name, None))

    def has_before_upload_loop(self):
        return self.__has_method("before_upload_loop")

    def has_after_upload_loop(self):
        return self.__has_method("after_upload_loop")

    def has_before_frame_upload(self):
        return self.__has_method("before_frame_upload")

    def has_after_frame_upload(self):
        return self.__has_method("after_frame_upload")
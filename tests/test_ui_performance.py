import queue
import unittest

from chat_bridge.app import App, _UI_EVENT_MAX_BATCH


class UiEventBudgetTests(unittest.TestCase):
    def test_ui_queue_yields_before_draining_an_unbounded_backlog(self):
        class FakeApp:
            _closing = False
            _drain_ui_events = App._drain_ui_events

            def __init__(self):
                self._ui_events = queue.Queue()
                self.after_calls = []

            def after(self, delay, callback):
                self.after_calls.append((delay, callback))

        fake = FakeApp()
        called = []
        for index in range(_UI_EVENT_MAX_BATCH + 10):
            fake._ui_events.put((called.append, (index,)))

        fake._drain_ui_events()

        self.assertLessEqual(len(called), _UI_EVENT_MAX_BATCH)
        self.assertGreater(fake._ui_events.qsize(), 0)
        self.assertEqual(fake.after_calls[-1][0], 1)


class ScrollBindingCleanupTests(unittest.TestCase):
    def test_destroy_removes_only_the_frames_global_bindings(self):
        try:
            import customtkinter as ctk
            from chat_bridge.ui.scrolling import SmoothScrollableFrame

            root = ctk.CTk()
        except Exception as exc:
            self.skipTest(f"Tk is unavailable in this test environment: {exc}")

        root.withdraw()
        try:
            before = str(root.tk.call("bind", "all", "<MouseWheel>"))
            frame = SmoothScrollableFrame(root)
            during = str(root.tk.call("bind", "all", "<MouseWheel>"))
            self.assertNotEqual(during, before)

            frame.destroy()
            root.update_idletasks()
            after = str(root.tk.call("bind", "all", "<MouseWheel>"))
            self.assertEqual(after, before)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()

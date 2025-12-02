from shiny import reactive

class _ClickedProducts:
    def __init__(self):
        self._rv = reactive.Value([])  # This will be a list of product dicts

    def get(self):
        return self._rv.get()

    def set(self, v):
        self._rv.set(v)

    def append(self, pid):
        # Accept only a pid and store it if not already present
        if pid is None:
            return
        cur = list(self._rv.get() or [])
        
        if pid not in cur:
            cur.append(pid)
        self._rv.set(cur)
        
    def remove(self, pid):
        # Remove the pid from the stored list of pids
        cur = list(self._rv.get() or [])
        cur = [p for p in cur if p != pid]
        self._rv.set(cur)
        
    def remove_all(self):
        self._rv.set([])
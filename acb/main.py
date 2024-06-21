from acb.adapters import import_adapter
from acb.depends import depends

App = import_adapter()
app = depends.get(App)

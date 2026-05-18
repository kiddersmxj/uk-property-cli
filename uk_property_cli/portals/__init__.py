from .base import SearchConfig
from .rightmove import RightmoveAdapter
from .espc import ESPCAdapter
from .zoopla import ZooplaAdapter

ADAPTERS = {
    "rightmove": RightmoveAdapter,
    "espc": ESPCAdapter,
    "zoopla": ZooplaAdapter,
}

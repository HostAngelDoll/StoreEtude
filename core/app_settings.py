from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class UIColumnConfig:
    width: int = 100
    locked: bool = False

@dataclass
class UIConfig:
    geometry: Optional[str] = None
    maximized: bool = True
    sidebar_visible: bool = True
    console_visible: bool = True
    auto_resize: bool = True
    show_construction_logs: bool = False
    theme: str = "Fusion"
    column_configs: Dict[str, Dict[str, UIColumnConfig]] = field(default_factory=dict)

@dataclass
class TelegramConfig:
    api_id: str = ""
    api_hash: str = ""
    chat_id: Optional[int] = None
    chat_name: str = ""

@dataclass
class APIConfig:
    enabled: bool = False
    port: int = 9090

@dataclass
class FirebaseConfig:
    db_url: str = ""
    db_ref_journals: str = ""
    credentials_path: str = ""

@dataclass
class AppSettings:
    base_dir_path: str = r"E:\_Internal"
    global_db_path: str = "_global.db"
    ui: UIConfig = field(default_factory=UIConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    api: APIConfig = field(default_factory=APIConfig)
    firebase: FirebaseConfig = field(default_factory=FirebaseConfig)

    def to_dict(self) -> Dict[str, Any]:
        def _to_dict(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
            elif isinstance(obj, dict):
                return {k: _to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_to_dict(x) for x in obj]
            return obj
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppSettings':
        def _from_dict(c, d):
            if hasattr(c, "__dataclass_fields__"):
                field_types = {f.name: f.type for f in c.__dataclass_fields__.values()}
                # This is a bit simplistic for complex types like Dict[str, Dict[str, UIColumnConfig]]
                kwargs = {}
                for k, v in d.items():
                    if k in field_types:
                        f_type = field_types[k]
                        if hasattr(f_type, "__dataclass_fields__"):
                            kwargs[k] = _from_dict(f_type, v)
                        elif k == "column_configs" and isinstance(v, dict):
                            # Special handling for column_configs
                            kwargs[k] = {tn: {cn: UIColumnConfig(**cv) for cn, cv in tc.items()} for tn, tc in v.items()}
                        else:
                            kwargs[k] = v
                return c(**kwargs)
            return d
        return _from_dict(cls, data)

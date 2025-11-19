from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml

@dataclass
class Transition:
    intent: Optional[str] = None
    guard: Optional[str] = None
    action: Optional[str] = None
    next: str = ""

@dataclass
class StateDef:
    name: str
    entry: Dict = field(default_factory=dict)
    timeout: Optional[int] = None
    transitions: List[Transition] = field(default_factory=list)

@dataclass
class FlowDoc:
    version: str
    metadata: Dict
    templates: Dict[str,str]
    actions: List[str]
    states: Dict[str,StateDef]
    fallbacks: Dict

def load_yaml(path: Path) -> FlowDoc:
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    states = {}
    for sname, sdef in doc.get("states", {}).items():
        trans = [Transition(**t) for t in sdef.get("transitions", []) or []]
        states[sname] = StateDef(name=sname, entry=sdef.get("entry", {}) or {}, 
                                 timeout=sdef.get("timeout"), transitions=trans)

    return FlowDoc(
        version=str(doc.get("version")),
        metadata=doc.get("metadata", {}),
        templates=doc.get("templates", {}),
        actions=doc.get("actions", []),
        states=states,
        fallbacks=doc.get("fallbacks", {}),
    )


# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Callable, Tuple, Dict
import importlib.util, sys
from pathlib import Path
import inspect as _inspect

def wrapper(call: Callable[[str], Any]) -> Callable[..., Any]:
    def _wrapped(message: str, **kwargs: Any) -> Any:
        return call(message, **kwargs)
    return _wrapped

def _repo_root() -> Path:
    p = Path(__file__).resolve()
    # Sobe até achar code/fluxos_intencao/chatbot.py
    for cand in [p.parent.parent, *p.parents]:
        if (cand / "code" / "fluxos_intencao" / "chatbot.py").exists():
            return cand
    return Path.cwd()

def _load_chatbot_module():
    # 1) Tenta importar como pacote (se seu "code" local estiver na frente)
    try:
        from code.fluxos_intencao import chatbot as cb  # type: ignore
        return cb, "pkg:code.fluxos_intencao.chatbot"
    except Exception:
        # 2) Importa pelo caminho de arquivo para evitar conflito com stdlib "code"
        root = _repo_root()
        mod_path = root / "code" / "fluxos_intencao" / "chatbot.py"
        if not mod_path.exists():
            raise ImportError(f"Não achei {mod_path}")
        spec = importlib.util.spec_from_file_location("curadobia_chatbot", mod_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Falha ao criar spec para {mod_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["curadobia_chatbot"] = module
        spec.loader.exec_module(module)
        return module, f"file:{mod_path}"

def load_pipeline(spec: Any = None) -> Tuple[Callable[..., Any], Dict[str, Any]]:
    cb, source = _load_chatbot_module()
    classify_intent = cb.classify_intent
    generate_response = cb.generate_response

    def respond(message: str, **kwargs: Any) -> str:
        meta: dict = kwargs.get("meta") or {}
        profile_json = meta.get("profile_json", {})
        pred = classify_intent(message) or {}
        intent = pred.get("intent") or "nao_entendi"

        params = _inspect.signature(generate_response).parameters
        call_kwargs: Dict[str, Any] = {}
        if "meta" in params: call_kwargs["meta"] = meta
        if "profile_json" in params: call_kwargs["profile_json"] = profile_json
        if "session_id" in params and "session_id" in kwargs:
            call_kwargs["session_id"] = kwargs["session_id"]

        return str(generate_response(intent, message, **call_kwargs))

    return wrapper(respond), {"source": source}

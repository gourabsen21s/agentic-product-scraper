# api/routes/plan_execute.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ..deps import get_session_manager
from runner.session_manager import SessionManager
from runner.action_executor import ActionExecutor
from runner.perception.yolo_perception import YOLOPerception
from reasoner.reasoner import Reasoner
from reasoner.schemas import ActionSchema
from runner.logger import log
import os
import traceback

router = APIRouter()
_perception = YOLOPerception()
_reasoner = Reasoner()

# Config
CONFIDENCE_THRESHOLD = float(os.getenv("REASONER_CONFIDENCE_THRESHOLD", "0.4"))

class PlanExecuteRequest(BaseModel):
    goal: str
    last_actions: Optional[list] = None
    force: Optional[bool] = False  # if true, will execute even if confidence low

class PlanExecuteResponse(BaseModel):
    session_id: str
    action: Dict[str, Any]
    execution_result: Optional[Dict[str, Any]] = None
    perception: Optional[Dict[str, Any]] = None
    reasoner_raw: Optional[Dict[str, Any]] = None

# Utility: convert target (id/coords/selector) to executor call
def _target_to_executor_call(target: Optional[Dict[str,str]], elements: list, executor: ActionExecutor, value: Optional[str]=None):
    """
    Returns (method_name, kwargs) or raises HTTPException if cannot map.
    """
    if target is None:
        raise HTTPException(status_code=400, detail="Action target required for this action")

    by = target.get("by")
    val = target.get("value")

    if by == "id":
        # find matching element
        for el in elements:
            if el.get("id") == val:
                bbox = el.get("bbox")
                # compute center coordinates
                x1, y1, x2, y2 = bbox
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                return ("click_xy", {"x": cx, "y": cy})
        raise HTTPException(status_code=400, detail=f"Element with id '{val}' not found in perception output")

    elif by == "coords":
        # coords expected as "x,y"
        try:
            x_str, y_str = val.split(",")
            x = int(float(x_str.strip()))
            y = int(float(y_str.strip()))
            return ("click_xy", {"x": x, "y": y})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid coords format: {val}")

    elif by == "selector":
        # use executor's selector-based primitives if available
        # prefer click_selector for clicks and type_selector for type actions
        return ("click_selector", {"selector": val})

    else:
        raise HTTPException(status_code=400, detail=f"Unknown target.by: {by}")

@router.post("/sessions/{session_id}/plan_execute", response_model=PlanExecuteResponse)
async def plan_and_execute(session_id: str, body: PlanExecuteRequest, sm: SessionManager = Depends(get_session_manager)):
    """
    Performs: snapshot -> perception -> reasoner -> execute (single action) -> return result
    Query param force=true will bypass low-confidence blocking.
    """
    log("INFO", "plan_exec_start", "Plan & Execute requested", session_id=session_id, goal=body.goal)

    meta = sm.get_session(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        # 1) capture screenshot (writes latest.png in session dir)
        screenshot_name = "latest.png"
        screenshot_path = await sm.snapshot(session_id, screenshot_name)

        # 2) perception
        elements = _perception.analyze(screenshot_path)
        elements_list = [e.dict() for e in elements]

        # 3) reasoning
        action_schema = _reasoner.plan_one(body.goal, elements_list, last_actions=body.last_actions or [])
        action_dict = action_schema.dict()
        log("INFO", "plan_exec_reasoned", "Reasoner produced action", session_id=session_id, action=action_dict)

        # 4) safety / confidence check
        if (not body.force) and (action_schema.confidence < CONFIDENCE_THRESHOLD):
            # do not execute low-confidence action
            log("WARN", "plan_exec_low_confidence", "Action below confidence threshold",
                session_id=session_id, confidence=action_schema.confidence, threshold=CONFIDENCE_THRESHOLD)
            return PlanExecuteResponse(
                session_id=session_id,
                action=action_dict,
                execution_result=None,
                perception={"elements": elements_list},
                reasoner_raw=action_dict
            )

        # 5) translate action -> call ActionExecutor
        page = meta.page
        if not page:
            raise HTTPException(status_code=500, detail="session page missing")

        executor = ActionExecutor(page, session_id=session_id)

        exec_result = None
        # dispatch based on action type
        a = action_schema.action
        target = action_schema.target.dict() if action_schema.target else None
        try:
            if a == "click":
                method, kwargs = _target_to_executor_call(target, elements_list, executor)
                # getattr returns the async method, so we await it
                exec_result = await getattr(executor, method)(**kwargs)
            elif a == "type":
                method, kwargs = _target_to_executor_call(target, elements_list, executor)
                # include text value
                kwargs["text"] = action_schema.value or ""
                # choose type_selector vs type_xy based on method returned
                if method == "click_selector":
                    # use type_selector if selector provided
                    exec_result = await executor.type_selector(kwargs["selector"], kwargs["text"])
                elif method == "click_xy":
                    exec_result = await executor.type_xy(kwargs["x"], kwargs["y"], kwargs["text"])
                else:
                    raise HTTPException(status_code=500, detail="Unsupported method mapping for type action")
            elif a == "navigate":
                url = action_schema.value
                exec_result = await executor.navigate(url)
            elif a == "scroll":
                # interpret target coords or use default
                if target and target.get("by") == "coords":
                    x_str, y_str = target.get("value").split(",")
                    exec_result = await executor.scroll(0, int(float(y_str.strip())))
                else:
                    exec_result = await executor.scroll(0, 500)
            elif a == "hover":
                method, kwargs = _target_to_executor_call(target, elements_list, executor)
                if method == "click_xy":
                    exec_result = await executor.hover(kwargs["x"], kwargs["y"])
                else:
                    raise HTTPException(status_code=400, detail="hover target mapping unsupported")
            elif a == "press_key":
                key = action_schema.value or "Enter"
                exec_result = await executor.press_key(key)
            elif a == "noop":
                exec_result = {"action_id": None, "status": "noop", "reason": action_schema.reason}
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported action type: {a}")
        except Exception as e:
            log("ERROR", "plan_exec_action_failed", "Action execution failed", session_id=session_id, error=str(e), tb=traceback.format_exc())
            # return error result but don't abort server
            raise HTTPException(status_code=500, detail=f"Action execution failed: {e}")

        # 6) return consolidated result
        response = PlanExecuteResponse(
            session_id=session_id,
            action=action_dict,
            execution_result=exec_result,
            perception={"elements": elements_list},
            reasoner_raw=action_dict
        )
        log("INFO", "plan_exec_done", "Plan & Execute completed", session_id=session_id, action=action_dict, exec_result=exec_result)
        return response

    except HTTPException:
        raise
    except Exception as e:
        log("ERROR", "plan_exec_error", "Unexpected error in plan_execute", session_id=session_id, error=str(e), tb=traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

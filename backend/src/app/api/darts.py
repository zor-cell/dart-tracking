from fastapi import APIRouter, WebSocket

router = APIRouter(prefix="/ws", tags=["Tracking"])

@router.websocket("/darts")
async def dart_tracking_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "Connection established..."})

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"echo": f"Received: {data}"})
    except Exception as e:
        print(f"Connection closed: {e}")
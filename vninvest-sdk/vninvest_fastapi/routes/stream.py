"""
FastAPI routes for real-time streaming endpoints.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field

from vninvest import (
    StreamChannel,
    StreamConfig,
    TenantContext,
    VninvestClient,
    get_tenant_context,
)

router = APIRouter(prefix="/stream", tags=["stream"])


class StreamConfigModel(BaseModel):
    """Request model for stream configuration."""
    symbols: list[str] = Field(..., min_length=1, description="List of stock symbols")
    channels: list[str] = Field(default=["price"], description="Channels: price, depth, trade, news, snapshot")
    provider_preference: list[str] = Field(default=["vci", "kbs"], description="Provider preference order")
    max_messages_per_second: int = Field(
        default=100, ge=1, le=1000, description="Max messages per second"
    )
    heartbeat_interval_seconds: int = Field(
        default=30, ge=5, le=300, description="Heartbeat interval"
    )


class StreamMessageModel(BaseModel):
    """Response model for stream messages."""
    channel: str
    symbol: str
    data: dict
    timestamp: str
    sequence: int
    provider: str


# Map string channels to StreamChannel enum
CHANNEL_MAP = {
    "price": StreamChannel.PRICE,
    "depth": StreamChannel.DEPTH,
    "trade": StreamChannel.TRADE,
    "news": StreamChannel.NEWS,
    "snapshot": StreamChannel.SNAPSHOT,
}


def get_required_scopes(channels: list[str]) -> list[str]:
    """Get required scopes for channels."""
    scope_map = {
        "price": "stream:price",
        "depth": "stream:depth",
        "trade": "stream:trade",
        "news": "news:read",
        "snapshot": "stream:price",
    }
    return [scope_map.get(ch, "stream:price") for ch in channels]


@router.websocket("/ws")
async def stream_websocket(
    websocket: WebSocket,
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    channels: str = Query(default="price", description="Comma-separated list of channels"),
    provider_preference: str = Query(
        default="vci,kbs", description="Comma-separated provider preference"
    ),
    max_messages_per_second: int = Query(default=100, ge=1, le=1000),
    heartbeat_interval_seconds: int = Query(default=30, ge=5, le=300),
):
    """
    WebSocket endpoint for real-time streaming.

    Query parameters:
    - **symbols**: Comma-separated symbols (e.g., "ACB,VCB,BID")
    - **channels**: Comma-separated channels (price,depth,trade,news,snapshot)
    - **provider_preference**: Comma-separated providers (vci,kbs)
    - **max_messages_per_second**: Rate limit
    - **heartbeat_interval_seconds**: Heartbeat interval
    """
    # Parse parameters
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    provider_list = [p.strip() for p in provider_preference.split(",") if p.strip()]

    if not symbol_list:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No symbols provided")
        return

    # Validate channels
    stream_channels = []
    for ch in channel_list:
        if ch in CHANNEL_MAP:
            stream_channels.append(CHANNEL_MAP[ch])
        else:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason=f"Invalid channel: {ch}"
            )
            return

    # Get client from app state
    client: VninvestClient = websocket.app.state.vninvest_client

    # Create stream config
    config = StreamConfig(
        tenant_id=client.context.tenant_id,
        symbols=symbol_list,
        channels=stream_channels,
        provider_preference=provider_list,
        max_messages_per_second=max_messages_per_second,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
    )

    # Create price stream
    price_stream = client.stream(config)

    # Check scopes for all channels
    required_scopes = get_required_scopes(channel_list)
    for scope in required_scopes:
        if not client.context.has_scope(scope):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason=f"Missing scope: {scope}"
            )
            return

    # Accept WebSocket connection
    await websocket.accept()

    try:
        # Subscribe to streams
        await price_stream.subscribe(symbol_list, stream_channels, provider_list)

        # Send confirmation
        await websocket.send_json({
            "type": "subscribed",
            "symbols": symbol_list,
            "channels": channel_list,
            "providers": provider_list,
        })

        # Stream messages
        async for message in price_stream:
            # Convert StreamMessage to JSON
            msg_data = {
                "type": "data",
                "channel": message.channel.value,
                "symbol": message.symbol,
                "data": message.data,
                "timestamp": message.timestamp.isoformat(),
                "sequence": message.sequence,
                "provider": message.provider,
            }
            await websocket.send_json(msg_data)

    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        # Send error and close
        import contextlib

        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        # Cleanup
        await price_stream.close()


@router.post(
    "/config",
    summary="Create stream configuration",
    description=(
        "Create a stream configuration for use with WebSocket. "
        "Requires appropriate stream scopes."
    ),
)
async def create_stream_config(
    request: StreamConfigModel,
    http_request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """
    Create a stream configuration.

    Returns a configuration object that can be used to establish a WebSocket connection.
    """
    # Validate channels and check scopes
    stream_channels = []
    for ch in request.channels:
        if ch in CHANNEL_MAP:
            stream_channels.append(CHANNEL_MAP[ch])
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid channel: {ch}",
            )

    # Check scopes
    required_scopes = get_required_scopes(request.channels)
    for scope in required_scopes:
        if not context.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token missing required scope: {scope}",
            )

    config = StreamConfig(
        tenant_id=context.tenant_id,
        symbols=[s.upper() for s in request.symbols],
        channels=stream_channels,
        provider_preference=request.provider_preference,
        max_messages_per_second=request.max_messages_per_second,
        heartbeat_interval_seconds=request.heartbeat_interval_seconds,
    )

    websocket_url = (
        f"/api/v1/stream/ws?symbols={','.join(config.symbols)}"
        f"&channels={','.join(request.channels)}"
        f"&provider_preference={','.join(config.provider_preference)}"
    )
    return {"config": config.model_dump(), "websocket_url": websocket_url}

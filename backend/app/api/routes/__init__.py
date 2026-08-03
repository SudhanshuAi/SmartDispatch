from fastapi import APIRouter

from app.api.routes import driver, drivers, guest, guests, matching, ops, realtime, trips, vehicles

api_router = APIRouter()
api_router.include_router(ops.router)
api_router.include_router(driver.router)
api_router.include_router(guest.router)
api_router.include_router(realtime.router)
api_router.include_router(vehicles.router)
api_router.include_router(drivers.router)
api_router.include_router(guests.router)
api_router.include_router(trips.router)
api_router.include_router(matching.router)

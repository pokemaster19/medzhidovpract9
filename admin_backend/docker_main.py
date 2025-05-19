from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
import json
import os
import uuid
import time
import asyncio
from datetime import datetime
from pathlib import Path
import threading

# Пути к файлам внутри Docker-контейнера
PRODUCTS_FILE = "/app/data/products.json"
ADMIN_STATIC_DIR = "/app/public/admin"
DOCS_STATIC_DIR = "/app/docs"

# Блокировка для безопасного доступа к файлу
file_lock = threading.Lock()

# Модели данных для чата
class ChatMessage(BaseModel):
    sender_type: str  # "user" или "admin"
    user_id: str
    text: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

# Менеджер WebSocket соединений
class ConnectionManager:
    def __init__(self):
        # Активные соединения
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {
            "admin": {},  # admin_id -> WebSocket
            "user": {}    # user_id -> WebSocket
        }
        # История сообщений (последние 50)
        self.message_history: List[ChatMessage] = []
        self.max_history_size = 50
    
    async def connect(self, websocket: WebSocket, client_type: str, client_id: str):
        await websocket.accept()
        if client_type not in self.active_connections:
            raise ValueError(f"Недопустимый тип клиента: {client_type}")
        self.active_connections[client_type][client_id] = websocket
        
        # Отправляем историю сообщений новому клиенту
        for message in self.message_history:
            await websocket.send_json(message.dict())
    
    def disconnect(self, client_type: str, client_id: str):
        if client_id in self.active_connections[client_type]:
            del self.active_connections[client_type][client_id]
    
    async def send_personal_message(self, message: ChatMessage, client_type: str, client_id: str):
        if client_id in self.active_connections[client_type]:
            await self.active_connections[client_type][client_id].send_json(message.dict())
    
    async def broadcast(self, message: ChatMessage):
        # Добавляем сообщение в историю
        self.message_history.append(message)
        # Ограничиваем размер истории
        if len(self.message_history) > self.max_history_size:
            self.message_history = self.message_history[-self.max_history_size:]
        
        # Отправляем сообщение всем пользователям
        for client_type in self.active_connections:
            for client_id, connection in self.active_connections[client_type].items():
                try:
                    await connection.send_json(message.dict())
                except Exception as e:
                    print(f"Ошибка при отправке сообщения клиенту {client_type}:{client_id}: {str(e)}")

# Создаем экземпляр менеджера соединений
manager = ConnectionManager()

app = FastAPI(
    title="Панель администратора API",
    description="API для управления товарами в интернет-магазине",
    version="1.0.0",
    docs_url="/admin/api/docs",
    redoc_url="/admin/api/redoc"
)

# Включение CORS для всех источников
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных для API
class Category(BaseModel):
    name: str

class ProductBase(BaseModel):
    name: str
    price: float
    description: str
    categories: List[str]

class ProductCreate(ProductBase):
    id: Optional[str] = None

class ProductUpdate(ProductBase):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None

class Product(ProductBase):
    id: str

# Функции для работы с данными
def read_products():
    """Чтение товаров из файла JSON"""
    if not os.path.exists(PRODUCTS_FILE):
        return []
    
    with file_lock:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

def write_products(products: List[Dict[str, Any]]):
    """Запись товаров в файл JSON"""
    with file_lock:
        # Убедимся, что директория существует
        os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)
        
        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)

def get_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    """Получение товара по ID"""
    products = read_products()
    for product in products:
        if product.get("id") == product_id:
            return product
    return None

def generate_unique_id() -> str:
    """Генерация уникального ID для товара"""
    return str(uuid.uuid4())

# API эндпоинты
@app.get("/admin/api/products", response_model=List[Product])
def get_all_products():
    """Получение всех товаров"""
    products = read_products()
    return products

@app.post("/admin/api/products", response_model=List[Product])
def add_products(products: List[ProductCreate]):
    """Добавление одного или нескольких товаров"""
    existing_products = read_products()
    
    # Получение существующих ID для проверки уникальности
    existing_ids = {product.get("id") for product in existing_products}
    
    added_products = []
    for product_data in products:
        product_dict = product_data.dict()
        
        # Если ID не указан или уже существует, генерируем новый
        if not product_dict.get("id") or product_dict.get("id") in existing_ids:
            product_dict["id"] = generate_unique_id()
        existing_ids.add(product_dict["id"])
        
        existing_products.append(product_dict)
        added_products.append(product_dict)
    
    write_products(existing_products)
    return added_products

@app.put("/admin/api/products/{product_id}", response_model=Product)
def update_product(product_id: str, product_update: ProductUpdate):
    """Обновление информации о товаре по ID"""
    products = read_products()
    product_index = None
    
    # Поиск индекса товара в списке
    for i, product in enumerate(products):
        if product.get("id") == product_id:
            product_index = i
            break
    
    if product_index is None:
        raise HTTPException(status_code=404, detail=f"Товар с ID {product_id} не найден")
    
    # Обновление полей товара
    update_data = product_update.dict(exclude_unset=True)
    current_product = products[product_index]
    
    for field, value in update_data.items():
        if value is not None:  # Обновляем только непустые поля
            current_product[field] = value
    
    write_products(products)
    return current_product

@app.delete("/admin/api/products/{product_id}", response_model=dict)
def delete_product(product_id: str):
    """Удаление товара по ID"""
    products = read_products()
    product_index = None
    
    # Поиск индекса товара в списке
    for i, product in enumerate(products):
        if product.get("id") == product_id:
            product_index = i
            break
    
    if product_index is None:
        raise HTTPException(status_code=404, detail=f"Товар с ID {product_id} не найден")
    
    # Удаление товара из списка
    removed_product = products.pop(product_index)
    write_products(products)
    
    return {"message": f"Товар с ID {product_id} успешно удален"}

# WebSocket эндпоинт для подключения к чату
@app.websocket("/ws/chat/{client_type}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_type: str, client_id: str):
    if client_type not in ["admin", "user"]:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await manager.connect(websocket, client_type, client_id)
    
    try:
        # Отправляем системное сообщение о подключении
        system_message = ChatMessage(
            sender_type="system",
            user_id="system",
            text=f"{'Администратор' if client_type == 'admin' else 'Пользователь'} присоединился к чату"
        )
        await manager.broadcast(system_message)
        
        while True:
            # Ожидаем сообщение от клиента
            data = await websocket.receive_text()
            
            try:
                # Пытаемся разобрать JSON
                message_data = json.loads(data)
                text = message_data.get("text", "").strip()
                
                # Проверяем, что сообщение не пустое
                if text:
                    message = ChatMessage(
                        sender_type=client_type,
                        user_id=client_id,
                        text=text
                    )
                    # Рассылаем сообщение всем подключенным клиентам
                    await manager.broadcast(message)
            except json.JSONDecodeError:
                # Если не JSON, просто используем как текст
                if data.strip():
                    message = ChatMessage(
                        sender_type=client_type,
                        user_id=client_id,
                        text=data
                    )
                    await manager.broadcast(message)
            
    except WebSocketDisconnect:
        # Отключаем клиента
        manager.disconnect(client_type, client_id)
        
        # Отправляем системное сообщение об отключении
        system_message = ChatMessage(
            sender_type="system",
            user_id="system",
            text=f"{'Администратор' if client_type == 'admin' else 'Пользователь'} покинул чат"
        )
        await manager.broadcast(system_message)
    
# API эндпоинт для получения истории сообщений чата
@app.get("/admin/api/chat/history")
async def get_chat_history():
    return manager.message_history

# Монтирование статических файлов для админки
app.mount("/admin", StaticFiles(directory=ADMIN_STATIC_DIR, html=True), name="admin")

# Монтирование документации API
app.mount("/docs", StaticFiles(directory=DOCS_STATIC_DIR, html=True), name="docs")

# Дополнительный маршрут для корневого URL
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return """
    <html>
        <head>
            <title>Админ-панель магазина</title>
            <meta http-equiv="refresh" content="0;url=/admin/" />
        </head>
        <body>
            <p>Перенаправление на админ-панель...</p>
        </body>
    </html>
    """

# Маршрут для скачивания OpenAPI-спецификации
@app.get("/admin/api/openapi.json")
async def get_open_api_endpoint():
    return JSONResponse(get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    ))
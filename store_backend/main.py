from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import os
from typing import List, Dict, Any, Optional

app = FastAPI(title="Магазин API")

# Включение CORS для всех источников
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Загрузка товаров из JSON файла
def load_products():
    products_path = "/workspace/data/products.json"
    if not os.path.exists(products_path):
        raise FileNotFoundError(f"Файл с товарами не найден: {products_path}")
    
    with open(products_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Простая эмуляция GraphQL с использованием POST запроса
async def process_graphql_query(query_str: str) -> Dict[str, Any]:
    """
    Обработка GraphQL запроса
    """
    # Простой парсер для запроса GraphQL
    products_query = "products" in query_str
    product_by_id_query = "product(id:" in query_str
    
    # Определяем, какие поля запрашиваются
    fields = []
    if "id" in query_str:
        fields.append("id")
    if "name" in query_str:
        fields.append("name")
    if "price" in query_str:
        fields.append("price")
    if "description" in query_str:
        fields.append("description")
    if "categories" in query_str:
        fields.append("categories")
    
    # Если полей не найдено, возвращаем все поля
    if not fields:
        fields = ["id", "name", "price", "description", "categories"]
    
    try:
        products_data = load_products()
        
        # Фильтруем поля
        filtered_products = []
        for product in products_data:
            filtered_product = {}
            for field in fields:
                if field in product:
                    filtered_product[field] = product[field]
            filtered_products.append(filtered_product)
        
        if product_by_id_query:
            # Извлекаем ID товара из запроса
            import re
            id_match = re.search(r'product\(id:\s*"([^"]+)"\)', query_str)
            if id_match:
                product_id = id_match.group(1)
                # Ищем товар по ID
                for product in filtered_products:
                    if product.get("id") == product_id:
                        return {"data": {"product": product}}
                return {"data": {"product": None}}
        
        if products_query:
            return {"data": {"products": filtered_products}}
        
        return {"errors": [{"message": "Неизвестный запрос GraphQL"}]}
        
    except Exception as e:
        return {"errors": [{"message": f"Ошибка при обработке GraphQL запроса: {str(e)}"}]}

# API эндпоинт для получения всех товаров
@app.get("/api/products")
def get_products():
    try:
        products = load_products()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки товаров: {str(e)}")

# Реализация GraphQL эндпоинта
@app.post("/graphql")
async def graphql_endpoint(request: Dict = Body(...)):
    """
    GraphQL эндпоинт для запросов
    """
    try:
        query = request.get("query", "")
        return await process_graphql_query(query)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"errors": [{"message": f"Ошибка сервера: {str(e)}"}]}
        )

# Монтирование статических файлов
app.mount("/", StaticFiles(directory="/workspace/public/store", html=True), name="static")

# Запуск приложения
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
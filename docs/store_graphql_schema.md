# GraphQL Схема Бэкенда Интернет-магазина

## Обзор

GraphQL API интернет-магазина позволяет выполнять гибкие запросы к данным товаров. В отличие от REST API, GraphQL позволяет запрашивать только те поля, которые нужны клиенту, что уменьшает объем передаваемых данных и повышает производительность.

## Базовый URL

```
http://localhost:3000/graphql
```

## Типы данных

### Тип `Product`

Представляет информацию о товаре.

| Поле | Тип | Описание |
|------|-----|----------|
| id | String | Уникальный идентификатор товара |
| name | String | Название товара |
| price | Float | Цена товара в рублях |
| description | String | Описание товара |
| categories | [String] | Список категорий товара |

## Запросы (Queries)

### `products`

Получает список всех товаров.

**Возвращаемый тип**: `[Product]`

**Пример запроса**:
```graphql
query {
  products {
    id
    name
    price
  }
}
```

**Пример ответа**:
```json
{
  "data": {
    "products": [
      {
        "id": "1",
        "name": "Ноутбук 'Молния'",
        "price": 99990.0
      },
      {
        "id": "2",
        "name": "Смартфон 'Галактика S25'",
        "price": 75500.0
      }
    ]
  }
}
```

### `product`

Получает товар по его ID.

**Аргументы**:
- `id` (String!, обязательный): ID товара

**Возвращаемый тип**: `Product`

**Пример запроса**:
```graphql
query {
  product(id: "1") {
    id
    name
    price
    description
    categories
  }
}
```

**Пример ответа**:
```json
{
  "data": {
    "product": {
      "id": "1",
      "name": "Ноутбук 'Молния'",
      "price": 99990.0,
      "description": "Сверхбыстрый ноутбук для профессионалов и геймеров.",
      "categories": ["Электроника", "Компьютеры"]
    }
  }
}
```

## Примеры использования

### Получение только имен и цен товаров

```graphql
query {
  products {
    name
    price
  }
}
```

### Получение товаров с категориями, без описания

```graphql
query {
  products {
    id
    name
    price
    categories
  }
}
```

### Получение полной информации о конкретном товаре

```graphql
query {
  product(id: "3") {
    id
    name
    price
    description
    categories
  }
}
```

## Использование в клиентском коде

```javascript
// Пример запроса с использованием fetch
async function fetchProductsGraphQL() {
  const query = `
    query {
      products {
        name
        price
        categories
      }
    }
  `;
  
  const response = await fetch('http://localhost:3000/graphql', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query })
  });
  
  const result = await response.json();
  
  if (result.errors) {
    throw new Error(result.errors[0].message);
  }
  
  return result.data.products;
}
```
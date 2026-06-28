USE text2sql_langgraph;

INSERT INTO users (username, email, password_hash, role) VALUES
('admin', 'admin@example.com', '$2b$12$EixZaYbB.rK4fl8x2q7Meu6Q6D2V5fF5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q', 'admin'),
('user1', 'user1@example.com', '$2b$12$EixZaYbB.rK4fl8x2q7Meu6Q6D2V5fF5Q5Q5Q5Q5Q5Q5Q5Q5Q', 'user'),
('user2', 'user2@example.com', '$2b$12$EixZaYbB.rK4fl8x2q7Meu6Q6D2V5fF5Q5Q5Q5Q5Q5Q5Q5Q5Q', 'user'),
('user3', 'user3@example.com', '$2b$12$EixZaYbB.rK4fl8x2q7Meu6Q6D2V5fF5Q5Q5Q5Q5Q5Q5Q5Q5Q', 'user');

INSERT INTO products (name, category, price, stock) VALUES
('笔记本电脑', '电子产品', 5999.00, 50),
('无线鼠标', '电子产品', 99.00, 200),
('机械键盘', '电子产品', 299.00, 100),
('显示器', '电子产品', 1299.00, 30),
('办公椅', '家具', 499.00, 80),
('办公桌', '家具', 1299.00, 40),
('台灯', '家具', 89.00, 150),
('打印机', '办公设备', 899.00, 25);

INSERT INTO orders (user_id, product_name, quantity, total_amount, status) VALUES
(1, '笔记本电脑', 1, 5999.00, 'completed'),
(1, '无线鼠标', 2, 198.00, 'completed'),
(2, '机械键盘', 1, 299.00, 'pending'),
(2, '显示器', 1, 1299.00, 'completed'),
(3, '办公椅', 2, 998.00, 'pending'),
(3, '办公桌', 1, 1299.00, 'completed'),
(4, '台灯', 3, 267.00, 'completed'),
(4, '打印机', 1, 899.00, 'pending'),
(1, '显示器', 1, 1299.00, 'pending'),
(2, '笔记本电脑', 1, 5999.00, 'completed');
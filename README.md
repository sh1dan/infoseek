# 🔍 InfoSeek

> Modern web application for news search and analysis with automatic PDF generation

[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18.2-blue.svg)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Repository:** [https://github.com/sh1dan/infoseek](https://github.com/sh1dan/infoseek)

**InfoSeek** is a full-featured application for searching news articles from the Polish news portal [RadioZET.pl](https://www.radiozet.pl), with automatic PDF generation and a modern premium dark-themed UI.

> **Note:** This is a university course project developed as part of academic coursework.

## ✨ Features

- 🔎 **Smart Search** — Search articles by keywords with customizable result count
- 📄 **Automatic PDF Generation** — Clean formatted article PDFs
- 🎨 **Premium UI** — Modern dark mode interface with glassmorphism effects
- ⚡ **Asynchronous Processing** — Background tasks via Celery
- 📊 **Search History** — Save all search queries with results
- 🐳 **Docker Ready** — Full containerization for easy deployment

## 🚀 Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Windows/Mac)
- Docker Compose (included with Docker Desktop)

### Installation and Setup

#### Windows (Recommended)

**First-time setup:**
```bash
setup.bat
```

**Subsequent launches:**
```bash
start.bat
```

#### Linux/Mac

```bash
# Start all services
docker-compose up --build -d

# Run database migrations
docker-compose exec backend python manage.py migrate
```

## 📖 Usage

### Search Format

InfoSeek supports flexible input format:

```
keyword, count
```

**Examples:**
- `Chopin, 5` — Find 5 articles about Chopin
- `Economy, 10 статей` — Find 10 articles about economy
- `Tech` — Find 3 articles by default

### Capabilities

1. **Search Articles** — Enter a keyword and article count
2. **View Results** — Track search progress in real-time
3. **Download PDFs** — Download any found article as PDF
4. **History** — Browse all previous searches with pagination

## 🏗️ Architecture

```
infoseek/
├── backend/              # Django REST API
│   ├── infoseek/        # Django main settings
│   └── search/          # Search application
│       ├── models.py    # Data models
│       ├── views.py     # API endpoints
│       ├── tasks.py     # Celery tasks
│       └── migrations/  # Database migrations
├── frontend/            # React application
│   ├── src/
│   │   ├── components/  # React components
│   │   └── services/    # API services
│   └── public/          # Static files
├── media/               # Generated PDF files
└── docker-compose.yml   # Docker configuration
```

## 🔧 Tech Stack

### Backend
- **Django 4.2+** — Web framework
- **Django REST Framework** — REST API
- **Celery** — Asynchronous task queue
- **PostgreSQL** — Database
- **Redis** — Message broker for Celery
- **Selenium** — Web scraping

### Frontend
- **React 18.2** — UI library
- **Tailwind CSS** — Styling
- **Axios** — HTTP client

### Infrastructure
- **Docker** — Containerization
- **Docker Compose** — Service orchestration

## 🌐 Application Access

After startup, the application is available at:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin
- **Selenium Grid**: http://localhost:4444

## 📝 Useful Commands

### Service Management

```bash
# Stop all services
docker-compose down

# Stop with data cleanup
docker-compose down -v

# Restart specific service
docker-compose restart backend
docker-compose restart frontend
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery_worker
```

### Database Operations

```bash
# Django shell
docker-compose exec backend python manage.py shell

# Create migrations
docker-compose exec backend python manage.py makemigrations

# Apply migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser
```

### Status Check

```bash
# Windows
check-services.bat

# Linux/Mac
docker-compose ps
```

## 🛠️ Development

### Backend Development

Backend code is located in `backend/`. Changes are applied automatically thanks to Docker volume mapping.

```bash
# Run only backend
docker-compose up backend db redis
```

### Frontend Development

Frontend code is located in `frontend/`. Hot-reload is enabled by default.

```bash
# Run only frontend
docker-compose up frontend
```

## ⚙️ Configuration

### Environment Variables

Main variables are configured in `docker-compose.yml`:

- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `SELENIUM_URL` — Selenium Grid URL
- `DEBUG` — Debug mode (1/0)
- `REACT_APP_API_URL` — Backend API URL for frontend

### Changing News Source

To change the news source, edit `backend/search/tasks.py`:

```python
search_url = f'https://www.radiozet.pl/Wyszukaj?q={keyword}'
```

You may also need to update article search selectors depending on the new site's structure.

## 🐛 Troubleshooting

### Docker Image Download Error (502 Bad Gateway)

```bash
# Option 1: Retry manually
docker pull selenium/standalone-chrome:latest
docker-compose up --build

# Option 2: Run without Selenium (for testing)
docker-compose -f docker-compose.no-selenium.yml up --build
```

### Port Already in Use

Change ports in `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Instead of 8000:8000
```

### Migration Issues

```bash
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

### Full Rebuild

```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🎓 Academic Project

This project was developed as part of a university course assignment. It demonstrates:

- Full-stack web development (Django + React)
- Docker containerization
- Asynchronous task processing
- Web scraping techniques
- Modern UI/UX design

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📧 Contact

For questions and suggestions, please create an issue in the [repository](https://github.com/sh1dan/infoseek/issues).

## 🔧 Git Setup

To push this project to GitHub, you'll need Git installed. See [GIT_SETUP.md](GIT_SETUP.md) for detailed instructions.

**Quick Git Installation (Windows):**
- Download from: https://git-scm.com/download/win
- Or use: `winget install --id Git.Git -e --source winget`

---

**Made with ❤️ for efficient news searching**

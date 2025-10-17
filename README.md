# ATS-Friendly CV Builder

An AI-powered web application for creating professional, ATS-optimized resumes and CVs. Built with FastAPI, modern JavaScript, and integrated with OpenAI for intelligent content suggestions.

## Features

- **AI-Powered Content Generation**: Leverage OpenAI to create compelling resume content
- **ATS Optimization**: Built-in ATS compatibility checking and optimization
- **Professional Templates**: Multiple professionally designed CV templates
- **PDF Export**: High-quality PDF generation and export
- **Cloud Storage**: Secure cloud storage for CVs (AWS S3, Firebase, or Supabase)
- **Real-time Preview**: Live preview of your CV as you build it
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Tech Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: Python SQL toolkit and Object-Relational Mapping (ORM)
- **PostgreSQL**: Primary database (with MongoDB support)
- **OpenAI API**: AI-powered content generation
- **Pydantic**: Data validation and settings management
- **JWT Authentication**: Secure token-based authentication

### Frontend
- **Vanilla JavaScript**: Modern ES6+ JavaScript
- **Tailwind CSS**: Utility-first CSS framework
- **Responsive Design**: Mobile-first approach

### DevOps & Deployment
- **Uvicorn**: ASGI web server implementation for production
- **Docker Ready**: Containerized deployment support
- **Heroku Compatible**: Ready for Heroku deployment

## Project Structure

```
├── app/
│   ├── config/          # Configuration files
│   │   ├── settings.py  # Application settings
│   │   ├── logging.py   # Logging configuration
│   │   └── __init__.py
│   ├── models/          # Database models
│   ├── routes/          # API route handlers
│   ├── services/        # Business logic services
│   ├── utils/           # Utility functions
│   ├── templates/       # HTML templates
│   └── static/          # Static assets
│       ├── css/         # Stylesheets
│       ├── js/          # JavaScript files
│       └── images/      # Image assets
├── requirements.txt     # Python dependencies
├── main.py             # Application entry point
├── .env.example        # Environment variables template
├── README.md           # Project documentation
└── Procfile            # Heroku deployment configuration
```

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL (or MongoDB)
- OpenAI API key
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ats-cv-builder
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Set up the database**
   ```bash
   # Using PostgreSQL
   createdb cv_builder_db

   # Run database migrations (when implemented)
   # alembic upgrade head
   ```

6. **Run the application**
   ```bash
   python main.py
   ```

7. **Open your browser**
   Navigate to `http://localhost:8000`

## Configuration

### Environment Variables

Key configuration options in `.env`:

- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: Your OpenAI API key for AI features
- `SECRET_KEY`: JWT secret key for authentication
- `AWS_ACCESS_KEY_ID`: AWS credentials for file storage
- `REDIS_HOST`: Redis server for caching

See `.env.example` for a complete list of configuration options.

## API Documentation

Once the application is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/api/v1/openapi.json

## Development

### Running in Development Mode

```bash
python main.py
```

The application will start with hot reload enabled for development.

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app/
isort app/
```

## Deployment

### Heroku Deployment

1. Create a Heroku app
2. Set environment variables in Heroku dashboard
3. Deploy using the Procfile

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, email support@atscvbuilder.com or create an issue in the repository.

## Roadmap

- [ ] User authentication and authorization
- [ ] Multiple CV templates
- [ ] Advanced ATS scoring
- [ ] CV sharing and collaboration
- [ ] Mobile app development
- [ ] Multi-language support
- [ ] Advanced analytics and insights

## Changelog

### Version 1.0.0
- Initial release
- Basic CV builder functionality
- AI-powered content suggestions
- PDF export capability
- Responsive web design
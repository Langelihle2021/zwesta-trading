#!/bin/bash
# Zwesta Trading v2 - Build All Components
# This script builds everything: Backend, Frontend, Mobile, Docker containers

set -e

echo "=========================================="
echo "Zwesta Trading v2 - Complete Build"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
MOBILE_DIR="$SCRIPT_DIR/mobile"
DOCKER_DIR="$SCRIPT_DIR/docker"

# Build options
BUILD_BACKEND=${1:-all}
BUILD_FRONTEND=${2:-all}
BUILD_MOBILE=${3:-all}
BUILD_DOCKER=${4:-all}

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Backup existing .env if it exists
backup_env() {
    if [ -f ".env" ]; then
        print_warning ".env file exists, backing up to .env.backup"
        cp .env .env.backup
    fi
}

# ===== BACKEND BUILD =====
build_backend() {
    print_header "Building Backend"
    
    if [ ! -d "$BACKEND_DIR" ]; then
        print_warning "Backend directory not found: $BACKEND_DIR"
        return 1
    fi
    
    cd "$BACKEND_DIR"
    
    # Create .env if it doesn't exist
    if [ ! -f ".env" ]; then
        print_warning "Creating .env from .env.example"
        cp .env.example .env
        print_warning "Edit .env with your credentials"
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    print_success "Python version: $PYTHON_VERSION"
    
    # Install dependencies
    print_success "Installing Python dependencies..."
    pip install -q -r requirements-minimal.txt 2>/dev/null || {
        print_warning "Some dependencies may require compilation"
        pip install -r requirements-minimal.txt
    }
    
    print_success "Backend build complete!"
    cd "$SCRIPT_DIR"
}

# ===== FRONTEND BUILD =====
build_frontend() {
    print_header "Building Frontend"
    
    if [ ! -d "$FRONTEND_DIR" ]; then
        print_warning "Frontend directory not found: $FRONTEND_DIR"
        return 1
    fi
    
    cd "$FRONTEND_DIR"
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_warning "Node.js not found. Install from https://nodejs.org/"
        return 1
    fi
    
    NODE_VERSION=$(node --version)
    print_success "Node.js version: $NODE_VERSION"
    
    # Install dependencies
    if [ ! -d "node_modules" ]; then
        print_success "Installing Node.js dependencies..."
        npm install
    else
        print_success "Node.js dependencies already installed"
    fi
    
    # Build
    print_success "Building React app..."
    npm run build
    
    print_success "Frontend build complete!"
    cd "$SCRIPT_DIR"
}

# ===== MOBILE BUILD =====
build_mobile() {
    print_header "Building Mobile App"
    
    if [ ! -d "$MOBILE_DIR" ]; then
        print_warning "Mobile directory not found: $MOBILE_DIR"
        return 1
    fi
    
    cd "$MOBILE_DIR"
    
    # Check Flutter
    if ! command -v flutter &> /dev/null; then
        print_warning "Flutter not found. Install from https://flutter.dev/"
        return 1
    fi
    
    FLUTTER_VERSION=$(flutter --version | head -1)
    print_success "Flutter version: $FLUTTER_VERSION"
    
    # Get dependencies
    print_success "Getting Flutter dependencies..."
    flutter pub get
    
    # Build APK
    print_success "Building Android APK (Release)..."
    flutter build apk --release --no-android-gradle-daemon
    
    if [ -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
        print_success "APK built: build/app/outputs/flutter-apk/app-release.apk"
    fi
    
    print_success "Mobile build complete!"
    cd "$SCRIPT_DIR"
}

# ===== DOCKER BUILD =====
build_docker() {
    print_header "Building Docker Images"
    
    if [ ! -d "$DOCKER_DIR" ]; then
        print_warning "Docker directory not found: $DOCKER_DIR"
        return 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found. Install from https://www.docker.com/"
        return 1
    fi
    
    DOCKER_VERSION=$(docker --version)
    print_success "Docker version: $DOCKER_VERSION"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_warning "Docker Compose not found"
        return 1
    fi
    
    COMPOSE_VERSION=$(docker-compose --version)
    print_success "Docker Compose version: $COMPOSE_VERSION"
    
    # Build images
    print_success "Building Backend image..."
    docker build -f "$DOCKER_DIR/Dockerfile.backend" -t zwesta/backend:latest .
    
    print_success "Building Frontend image..."
    docker build -f "$DOCKER_DIR/Dockerfile.frontend" -t zwesta/frontend:latest .
    
    print_success "Building Mobile image..."
    docker build -f "$DOCKER_DIR/Dockerfile.mobile" -t zwesta/mobile:latest .
    
    print_success "Docker build complete!"
    
    # List images
    echo ""
    print_success "Built images:"
    docker images | grep zwesta
}

# ===== MAIN EXECUTION =====

case "${BUILD_BACKEND}" in
    all|backend)
        build_backend
        ;;
    skip)
        print_warning "Skipping Backend"
        ;;
esac

case "${BUILD_FRONTEND}" in
    all|frontend)
        build_frontend
        ;;
    skip)
        print_warning "Skipping Frontend"
        ;;
esac

case "${BUILD_MOBILE}" in
    all|mobile)
        build_mobile
        ;;
    skip)
        print_warning "Skipping Mobile"
        ;;
esac

case "${BUILD_DOCKER}" in
    all|docker)
        build_docker
        ;;
    skip)
        print_warning "Skipping Docker"
        ;;
esac

# Final status
print_header "Build Summary"
echo -e "${GREEN}✓ All builds complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Backend: cd backend && python app_simple.py"
echo "2. Frontend: cd frontend && npm run dev"
echo "3. Mobile: cd mobile && flutter run"
echo "4. Docker: docker-compose up -d"
echo ""
echo "For more info, see: INDEX.md or QUICK_START.md"

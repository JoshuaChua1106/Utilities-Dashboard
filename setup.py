#!/usr/bin/env python3
"""
Utilities Tracker Setup Script

This script sets up the Utilities Tracker application for local development.
It creates the necessary directory structure, initializes the database,
and prepares configuration files.
"""

from setuptools import setup, find_packages
import os
from pathlib import Path

# Read README for long description
def read_readme():
    readme_path = Path(__file__).parent / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return "A comprehensive utility expense tracking application"

# Read requirements
def read_requirements():
    req_path = Path(__file__).parent / "requirements.txt"
    if req_path.exists():
        with open(req_path) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="utilities-tracker",
    version="1.0.0",
    description="Automated utility expense tracking with email integration and analytics",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Utilities Tracker Team",
    author_email="contact@utilities-tracker.com",
    url="https://github.com/your-org/utilities-tracker",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial",
        "Topic :: Utilities",
    ],
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "pre-commit>=3.0.0",
        ],
        "aws": [
            "boto3>=1.34.0",
            "awscli>=1.29.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "utilities-tracker=local_dev.init_db:main",
            "ut-fetch=email_fetcher.fetch_invoices:main",
            "ut-parse=pdf_parser.parse_pdfs:main",
            "ut-serve=web_app.backend.app:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.yaml", "*.yml", "*.md", "*.txt"],
        "config": ["*.json", "templates/*.json"],
        "powerbi_dashboard": ["*.pbix"],
    },
    zip_safe=False,
)
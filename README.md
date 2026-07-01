README.md

🚀 AI DevOps On-Call Agent

-----------------------------------------------------

Hero Section
Badges
Project Overview

-----------------------------------------------------

🎯 Problem Statement

Why traditional monitoring is not enough

-----------------------------------------------------

🚀 Solution

AI DevOps On-Call Agent

-----------------------------------------------------

🏗 Current Architecture

(Mermaid Diagram)

-----------------------------------------------------

🚀 Final Vision

(Mermaid Diagram)

-----------------------------------------------------

⚙ End-to-End Workflow

(Mermaid Sequence Diagram)

-----------------------------------------------------

🧩 Current Features

✅ Kubernetes Diagnostics

✅ Rule Based RCA

✅ Intelligent Event Filtering

✅ Git Analyzer

✅ Fix Planner

-----------------------------------------------------

📂 Project Structure

app/
 api/
 services/
 clients/
 models/

and responsibility of each folder

-----------------------------------------------------

🧠 Rule Engine Capabilities

ImagePullBackOff

CrashLoopBackOff

OOMKilled

Probe Failure

Scheduling Failure

Node Failure

PVC Failure

Restart Count

Deployment Health

-----------------------------------------------------

🤖 Why Rule-Based Before AI?

This is the section that judges will love.

Explain

Rule Based
↓

Cheap

↓

Fast

↓

Deterministic

↓

OpenAI only for unknown cases

-----------------------------------------------------

🔄 Automation Pipeline

Incident

↓

Diagnostics

↓

Rule Engine

↓

Git Analyzer

↓

Fix Plan

↓

GitHub

↓

PR

↓

Human Approval

↓

GitHub Actions

↓

AKS

-----------------------------------------------------

📸 Sample Request

POST /analyze

-----------------------------------------------------

📸 Sample Response

Healthy

ImagePullBackOff

-----------------------------------------------------

🛣 Roadmap

Phase 1 ✔

Phase 2 ✔

Phase 3 ✔

Phase 4 ✔

GitHub Automation (In Progress)

OpenAI (Planned)

-----------------------------------------------------

🏆 Hackathon Highlights

Production Architecture

Modular Design

SRP

Deterministic RCA

AI only where needed

Auto PR

GitOps

AKS

-----------------------------------------------------

👨‍💻 Tech Stack

FastAPI

Python

Kubernetes SDK

AKS

GitHub API

OpenAI

Docker

GitHub Actions

-----------------------------------------------------

📄 License


Incident Management System
           │
           ▼
      AI DevOps Agent
           │
 ┌─────────┼──────────┐
 │         │          │
 ▼         ▼          ▼
K8s     Rule RCA   Git Analyzer
 │         │          │
 └─────────┼──────────┘
           ▼
        Fix Planner
           ▼
     GitHub Client
           ▼
     Pull Request
           ▼
 Human Approval
           ▼
 GitHub Actions
           ▼
      Deploy AKS
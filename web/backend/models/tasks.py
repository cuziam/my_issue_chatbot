"""Pydantic models for task-related endpoints."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class TaskSummary(BaseModel):
    id: str
    name: str
    status: str
    assignees: list[str]  # usernames
    tags: list[str]
    has_report: bool
    has_patch_review: bool
    has_context: bool
    url: str


class TaskDetail(TaskSummary):
    description: str
    markdown_description: str
    custom_fields: dict
    comments: list[dict]
    attachments: list[dict]
    linked_docs: list[dict]
    report_content: Optional[str] = None
    patch_review_content: Optional[str] = None
    context_content: Optional[str] = None
    patch_diff_content: Optional[str] = None


class FetchRequest(BaseModel):
    task_id: str

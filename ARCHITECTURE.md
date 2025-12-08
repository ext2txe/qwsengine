📘 ARCHITECTURE.md
QwsEngine Architecture

A high-level overview of the system structure, control flow, and extension boundaries.

1. Overview

QwsEngine is a two-window browser automation environment built on PySide6 and QWebEngineView.
Its architecture is designed around:

A Browser Window for interactive browsing

A Controller Window for automation and script execution

A Script Management System for workflow definition

A modular UI layer for menus, tabs, and toolbars

Layered abstractions that separate raw browser operations from higher-level automation features

This document explains how the components interact and where new features should be added.

2. High-Level Component Diagram
   ┌───────────────────┐
   │    app.py         │
   │  (entrypoint)     │
   └─────────┬─────────┘
             │
             ▼
   ┌───────────────────┐
   │  BrowserWindow     │◀────────────────┐
   │ (main_window.py)   │                 │
   └──┬───────────┬────┘                 │
      │           │                       │
      ▼           ▼                       │
┌──────────┐  ┌────────────┐              │
│TabManager│  │Browser tab  │              │
│(UI layer)│  │(browser_tab)│              │
└──────┬───┘  └──────┬─────┘              │
       │             │                     │
       ▼             ▼                     │
┌────────────────────────────────────────┐ │
│      Browser Operations Layer          │ │
│        (browser_operations.py)         │ │
└────────────────────────────────────────┘ │
                                           │
                   ┌─────────────────────┐ │
                   │ ControllerWindow    │─┘
                   │ (controller_window) │
                   └──────────┬──────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │   Script System        │
                  │ script_manager.py      │
                  │ script_management_ui   │
                  │ controller_script.py   │
                  └────────────────────────┘

3. Core Modules and Responsibilities
3.1 app.py (Entrypoint)

Creates the QApplication

Initializes settings + logging

Launches:

BrowserWindow

ControllerWindow

3.2 Browser Window – main_window.py

Responsibilities:

Tab lifecycle (open/close/switch)

Toolbar / menu wiring

Interaction with:

Script playback

Controller commands

Browser operations layer

High-level application state management

3.3 Tabs – browser_tab.py

Each tab contains:

A single QWebEngineView

Tab-specific navigation & DOM access

Helpers for JS evaluation

Signals to communicate with BrowserWindow

3.4 Browser Operations – browser_operations.py

This is the automation abstraction layer.

Provides reusable operations like:

Navigate to URL

Execute JS

Wait for load

Extract values / DOM interaction

Tab management from scripts

Used by:

Scripts

Controller

Future automation modules

4. Controller Window

File: controller_window.py

Acts as a remote control panel for BrowserWindow.

Capabilities:

Run scripts

Pause/resume/stop scripts

Step through actions

Send controller actions (e.g., “navigate”, “capture value”, etc.)

Glue logic is in:

controller_script.py

5. Scripts: Loading, UI, Execution
5.1 ScriptManager (script_manager.py)

Loads JSON scripts from:

scripts/ folder in project

User directory: ~/.qwsengine/scripts/

Validates and persists metadata

Provides an API for:

Retrieving actions

Running scripts

Storing execution history (future feature)

5.2 Script Management UI (script_management_ui.py)

UI to:

List scripts

Select scripts

Run/pause/stop scripts

View configuration

5.3 ControllerScript (controller_script.py)

Responsible for:

Converting script JSON actions into operations

Advancing the script cursor

Handling errors and evaluation results

6. Settings & Logging
settings.py / settings_dialog.py

Provide persistent configuration for:

Browser defaults

Window layout

Future automation behavior

log_manager.py

Centralized logging utilities for:

Application lifecycle

Controller events

Script execution

7. Request Interceptor

File: request_interceptor.py

Intercepts outbound HTTP requests from QWebEngine:

Useful for debugging

Can support future filtering features

Integrated into BrowserWindow

8. UI Layer — ui/ Package

The UI helpers formalize menu/toolbar/tab creation.

ui/
  menu_builder.py
  toolbar_builder.py
  tab_manager.py


These allow:

Consistent UI structure

Centralized maintenance of menu/toolbar actions

Simplified extension of UI features

9. Experimental Modules

These modules are not part of the core system:

config8r.py

processors.py

scopes.py

They provide:

Prototype extraction interfaces

DOM analysis tools

Pipeline-style HTML processors

Safe to ignore unless explicitly working on deep automation tooling.

10. Extension Summary

Use this table as a quick reference:

	      
 To modify…                         Change  here
Menus	                            ui/menu_builder.py
Toolbar	                            ui/toolbar_builder.py
Tab behavior	                    browser_tab .py
Browser automation	                browser_operation   s.py
Settings storage	                settings.py
Settings UI	                        settings_dialog.py
Script format	                    script_manage   r.py, controller_script.py
Script UI	                        script_management_ui.py
Controller actions	                controller_window.py, controller_script.py
---
name: dotcrypt
description: A document watermarking and identification workspace.
colors:
  ink: "#202b33"
  primary: "#253c47"
  primary-hover: "#375661"
  terracotta: "#d66d46"
  focus: "#cc5e34"
  background: "#f7f7f3"
  surface: "#ffffff"
  secondary-surface: "#edf0ed"
  muted: "#657078"
  border: "#dce1df"
typography:
  heading:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "38px"
    fontWeight: 600
    lineHeight: 1.18
    letterSpacing: "-0.035em"
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  label:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "12px"
    fontWeight: 600
rounded:
  field: "6px"
  dropzone: "9px"
  workspace: "14px"
spacing:
  mobile-gutter: "20px"
  desktop-gutter: "40px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.field}"
    padding: "0 20px"
    height: "46px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  input:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.field}"
    padding: "0 13px"
    height: "46px"
  workspace:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.workspace}"
---

# Design System: dotcrypt

## Overview

**Creative North Star: "A precise document workspace"**

The interface is technical and precise, with crisp, tactile controls. Deep ink, warm white surfaces, and restrained terracotta accents support a clear workspace for watermarking and identification.

**Key Characteristics:**
- Two focused tasks with a shared top navigation.
- Clear labels, direct actions, and feedback next to each workflow.
- Flat, bordered surfaces with restrained depth.

## Colors

Deep ink carries the primary text and action; warm terracotta marks the brand and active navigation, while a related accent marks focus. Warm off-white surrounds white and pale green-gray work surfaces. Muted text and light borders provide hierarchy without competing with the actions.

## Typography

The interface uses self-hosted DM Sans for headings, body text, and labels, with a sans-serif fallback. Desktop page headings are 38px and use weight 600; at the small-screen breakpoint they are 31px. Body text is 14px, with 12px labels and supporting details. Recipient references use a system monospace face to distinguish the identifier.

## Layout

The main workspace is at most 1240px wide, with 40px desktop gutters and 20px small-screen gutters. The create view pairs a form with a 340px document panel; at narrower widths the panel shrinks, then is hidden on small screens. The identification view stacks its input and output panels on narrower screens. Form fields stack on small screens, and tables scroll horizontally.

## Elevation & Depth

The workspace is mostly flat, using borders and tonal layering. The document preview has a subtle offset shadow to distinguish the represented page from its panel.

## Shapes

Fields and buttons use 6px corners, drop zones use 9px corners, and the main workspace uses 14px corners. The brand combines four slightly rotated squares with a lowercase wordmark and terracotta full stop.

## Components

### Buttons

The primary action is deep ink with white text, 6px corners, a 46px minimum height, and 20px horizontal padding. Hover lightens the background; disabled buttons fade and show a wait cursor. Keyboard focus uses a 3px terracotta outline with a 4px offset.

### Inputs and drop zones

Text inputs are 46px high with a light border, white background, and visible labels. Dashed drop zones support file selection and drag-and-drop; their background and border change on hover or drag-over. Feedback appears beside the affected workflow.

### Navigation

The top navigation uses muted labels and a terracotta underline on the active item. The selected view receives focus when changed through the navigation.

### Document and result panels

The create view presents a document preview on a pale secondary surface. The identify view replaces its empty state with recipient details after a successful scan. The create form retains its contents after download.

## Do's and Don'ts

### Do:
- **Do** keep labels, feedback, and keyboard focus visible.
- **Do** use the existing navy, warm white, and terracotta palette.
- **Do** preserve the lowercase wordmark and square brand mark.

### Don't:
- **Don't** introduce unverified claims about physical watermark reliability.
- **Don't** change the existing layout or palette as part of a naming-only update.

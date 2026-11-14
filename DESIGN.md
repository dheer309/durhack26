# Trace design system

The workspace is an Operate surface: two direct tasks, watermark and identify. A top navigation replaces the previous sidebar. Navy ink, warm white surfaces and restrained terracotta accents give the workspace a clear, calm hierarchy. The reliability section has been removed as requested.

## Tokens

- Font: self-hosted DM Sans, 14px body; 38px desktop and 31px mobile page headings.
- Background: `#f7f7f3`; panel: `#ffffff`; secondary panel: `#edf0ed`.
- Text: `#202b33`; muted: `#657078`; accent: `#d66d46`; primary action: `#253c47`.
- Borders: `#dce1df`; field radius: 6px; workspace radius: 14px.
- Content width: 1240px; desktop outer space: 40px; mobile: 20px.

## Components and behavior

Forms use explicit labels and native inputs. File inputs support selection and drag/drop. Loading replaces the button label; success and error messages sit beside the affected workflow. The create form retains its contents after download. The identify screen replaces its empty state with a recipient result. Keyboard navigation shows a 3px terracotta focus outline. On mobile the summary panel is omitted, forms stack, and tables scroll horizontally.

## Assets

`app/static/fonts/dm-sans.ttf` is sourced from Google Fonts (DM Sans). SVG icons use a consistent 1.65px stroke.

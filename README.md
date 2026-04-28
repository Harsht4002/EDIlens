# Healthcare EDI (X12) Parser - Prototype

A minimal web app that parses EDI X12 files into JSON and provides AI explanations via Google Gemini.

## Features

- **File/Text Input**: Paste raw EDI or type in textarea
- **Basic Parser**: Splits by `~` (segments) and `*` (elements), flat structure
- **Simple Error Detection**: Too few elements, invalid numeric fields
- **AI Explanation**: Click any segment or error to get a plain-English explanation from Gemini


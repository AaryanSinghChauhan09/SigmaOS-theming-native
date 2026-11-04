//! Color palette management with advanced features
//! Follows: Composition Over Inheritance, Open-Closed Principle

use std::collections::HashMap;

/// Color representation with multiple formats
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

impl Color {
    pub fn new(r: u8, g: u8, b: u8, a: u8) -> Self {
        Color { r, g, b, a }
    }

    pub fn rgb(r: u8, g: u8, b: u8) -> Self {
        Color::new(r, g, b, 255)
    }

    pub fn to_hex(&self) -> String {
        format!("#{:02X}{:02X}{:02X}", self.r, self.g, self.b)
    }

    pub fn to_rgba(&self) -> String {
        format!("rgba({}, {}, {}, {})", self.r, self.g, self.b, self.a)
    }

    pub fn blend(&self, other: Color, factor: f32) -> Color {
        let factor = factor.clamp(0.0, 1.0);
        Color {
            r: (self.r as f32 * (1.0 - factor) + other.r as f32 * factor) as u8,
            g: (self.g as f32 * (1.0 - factor) + other.g as f32 * factor) as u8,
            b: (self.b as f32 * (1.0 - factor) + other.b as f32 * factor) as u8,
            a: (self.a as f32 * (1.0 - factor) + other.a as f32 * factor) as u8,
        }
    }
}

/// Complete color palette
#[derive(Debug, Clone)]
pub struct ColorPalette {
    pub primary: Color,
    pub secondary: Color,
    pub background: Color,
    pub foreground: Color,
    pub accent: Color,
    pub success: Color,
    pub warning: Color,
    pub error: Color,
    pub custom: HashMap<String, Color>,
}

impl Default for ColorPalette {
    fn default() -> Self {
        ColorPalette {
            primary: Color::rgb(0, 120, 215),
            secondary: Color::rgb(0, 80, 150),
            background: Color::rgb(255, 255, 255),
            foreground: Color::rgb(0, 0, 0),
            accent: Color::rgb(255, 100, 0),
            success: Color::rgb(40, 167, 69),
            warning: Color::rgb(255, 193, 7),
            error: Color::rgb(220, 53, 69),
            custom: HashMap::new(),
        }
    }
}

impl ColorPalette {
    pub fn set_custom(&mut self, name: String, color: Color) {
        self.custom.insert(name, color);
    }

    pub fn get_custom(&self, name: &str) -> Option<&Color> {
        self.custom.get(name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_color_blend() {
        let c1 = Color::rgb(255, 0, 0);
        let c2 = Color::rgb(0, 255, 0);
        let blended = c1.blend(c2, 0.5);
        assert!(blended.r > 100 && blended.r < 150);
    }
}

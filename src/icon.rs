//! Icon theme management
//! Follows: Interface Segregation, Single Responsibility

use std::path::PathBuf;

/// Icon size specification
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum IconSize {
    Small,
    Medium,
    Large,
    XLarge,
    Custom(u32),
}

impl IconSize {
    pub fn pixels(&self) -> u32 {
        match self {
            IconSize::Small => 16,
            IconSize::Medium => 32,
            IconSize::Large => 48,
            IconSize::XLarge => 64,
            IconSize::Custom(size) => *size,
        }
    }
}

/// Icon specification
#[derive(Debug, Clone)]
pub struct Icon {
    pub name: String,
    pub path: PathBuf,
    pub sizes: Vec<IconSize>,
}

impl Icon {
    pub fn new(name: String, path: PathBuf) -> Self {
        Icon {
            name,
            path,
            sizes: vec![IconSize::Medium],
        }
    }

    pub fn add_size(&mut self, size: IconSize) {
        if !self.sizes.contains(&size) {
            self.sizes.push(size);
        }
    }
}

/// Icon theme
pub struct IconTheme {
    pub name: String,
    icons: Vec<Icon>,
}

impl IconTheme {
    pub fn new(name: String) -> Self {
        IconTheme {
            name,
            icons: Vec::new(),
        }
    }

    pub fn add_icon(&mut self, icon: Icon) {
        self.icons.push(icon);
    }

    pub fn find_icon(&self, name: &str, size: IconSize) -> Option<&Icon> {
        self.icons.iter()
            .find(|icon| icon.name == name && icon.sizes.contains(&size))
    }

    pub fn list_icons(&self) -> Vec<&str> {
        self.icons.iter().map(|icon| icon.name.as_str()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_icon_theme() {
        let mut theme = IconTheme::new("Test".to_string());
        let icon = Icon::new("test".to_string(), PathBuf::from("/test.png"));
        theme.add_icon(icon);
        assert_eq!(theme.list_icons().len(), 1);
    }
}

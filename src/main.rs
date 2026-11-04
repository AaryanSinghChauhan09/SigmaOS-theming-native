mod config;
mod error;
mod service;
mod palette;
mod icon;

use config::Config;
use service::Service;
use palette::{ColorPalette, Color};
use icon::{IconTheme, Icon, IconSize};
use std::path::PathBuf;
use anyhow::Result;

fn main() -> Result<()> {
    env_logger::init();
    
    let config = Config::default();
    let mut service = Service::new(config);
    
    service.start()?;
    println!("Service started successfully");
    
    // Demonstrate color palette
    let palette = ColorPalette::default();
    println!("Primary color: {}", palette.primary.to_hex());
    
    // Demonstrate icon theme
    let mut theme = IconTheme::new("SigmaOS Default".to_string());
    let icon = Icon::new("test".to_string(), PathBuf::from("/test.png"));
    theme.add_icon(icon);
    println!("Icon theme: {} icons", theme.list_icons().len());
    
    service.stop()?;
    println!("Service stopped successfully");
    
    Ok(())
}

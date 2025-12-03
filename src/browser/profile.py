from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ViewportSize(BaseModel):
    width: int = 1280
    height: int = 720

class BrowserProfile(BaseModel):
    """
    Configuration for the browser session.
    """
    model_config = ConfigDict(extra='ignore')

    headless: bool = False
    browser_type: str = "chromium" # chromium, firefox, webkit
    user_agent: Optional[str] = None
    viewport: ViewportSize = Field(default_factory=ViewportSize)
    
    # Security & Anti-detection
    disable_security: bool = True
    
    # Network
    proxy: Optional[Dict[str, str]] = None
    
    # Downloads
    downloads_path: Optional[str] = None
    
    # Persistence
    user_data_dir: Optional[str] = None
    
    # Optimization
    block_resources: bool = True
    
    # Chrome Args
    extra_args: List[str] = Field(default_factory=list)

    def get_playwright_args(self) -> List[str]:
        # Consolidated arguments from browser-use for maximum stealth and stability
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--disable-background-timer-throttling',
            '--disable-popup-blocking',
            '--disable-renderer-backgrounding',
            '--disable-background-networking',
            '--disable-backgrounding-occluded-windows',
            '--disable-ipc-flooding-protection',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--enable-features=NetworkService,NetworkServiceInProcess',
            '--force-color-profile=srgb',
            '--metrics-recording-only',
            '--password-store=basic',
            '--use-mock-keychain',
            '--hide-scrollbars', # Keep scrollbars hidden for cleaner screenshots, or remove if needed
            '--mute-audio',
        ]
        
        if self.disable_security:
            args.extend([
                '--disable-web-security',
                '--disable-site-isolation-trials',
                '--ignore-certificate-errors',
                '--disable-features=IsolateOrigins,site-per-process',
            ])
            
        if self.user_agent:
            args.append(f'--user-agent={self.user_agent}')
            
        args.extend(self.extra_args)
        return args

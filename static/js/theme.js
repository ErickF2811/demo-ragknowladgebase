/**
 * Theme toggle functionality
 * Handles switching between light and dark modes and persisting preference
 */

const ThemeManager = {
    getPreferredTheme() {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    },

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        // Also set bootstrap theme if pertinent, though we are using custom styles heavily
        document.documentElement.setAttribute('data-bs-theme', theme); 
        localStorage.setItem('theme', theme);
        
        // Dispatch event for other components (like charts) to update
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
        
        this.updateToggleButton(theme);
    },

    toggle() {
        const current = this.getPreferredTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        this.setTheme(next);
    },

    updateToggleButton(theme) {
        const btn = document.getElementById('theme-toggle-btn');
        if (!btn) return;
        
        // Update icon based on theme
        // Sun for light, Moon for dark
        const icon = theme === 'dark' 
            ? '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'
            : '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
            
        btn.innerHTML = icon;
        btn.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    },

    init() {
        const theme = this.getPreferredTheme();
        this.setTheme(theme);
        
        // Listen for system changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(this.getPreferredTheme());
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    
    // Attach listener to toggle button if it exists
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.addEventListener('click', () => ThemeManager.toggle());
    }
});

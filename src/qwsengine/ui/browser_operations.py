# qwsengine/browser_operations.py

import json
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QPainter, QImage
from PySide6.QtCore import QRect, QTimer


class BrowserOperations:
    """
    Utility class for common browser operations across tabs/windows.
    Handles screenshots, HTML saving, full-page captures, and page readiness checks.
    """
    
    def __init__(self, settings_manager=None, status_callback=None, command_callback=None):
        """
        Args:
            settings_manager: Settings manager instance (optional)
            status_callback: Function to call for status messages (optional)
                           Signature: callback(message, level="INFO", timeout_ms=5000)
        """
        self.settings_manager = settings_manager
        self.status_callback = status_callback or self._default_status
        # Optional callback for logging to a "command log" UI (Controller window)
        # Signature: callback(message: str)
        self.command_callback = command_callback
        
        # State for full-page screenshots
        self._fps_busy = False
        self._fps_img = None
        self._fps_painter = None
        self._fps_positions = None
        self._fps_dpr = None
        self._fps_vw = None
        self._fps_vh = None
        self._fps_tw = None
        self._fps_th = None
        self._fps_target = None
        self._fps_tab = None
    
    def _default_status(self, message, level="INFO", timeout_ms=5000):
        """Default status handler if none provided"""
        print(f"[{level}] {message}")
    
    def _log_error(self, context: str, message: str, extra: str = ""):
        """Helper to log errors via settings manager"""
        if self.settings_manager and hasattr(self.settings_manager, "log_error"):
            self.settings_manager.log_error(context, message, extra)
    
    def _log_system_event(self, context: str, event: str, details: str = ""):
        """Helper to log system events via settings manager"""
        if self.settings_manager and hasattr(self.settings_manager, "log_system_event"):
            self.settings_manager.log_system_event(context, event, details)
    
    def is_browser_ready(self, tab=None, callback=None, show_warning=True):
        """
        Check if browser is ready for operations.
        
        Args:
            tab: The tab widget to check (must have 'browser' or 'view' attribute)
            callback: Function(view) to call if browser is ready
            show_warning: Whether to show status warnings
        
        Returns:
            bool if callback is None (synchronous check)
            None if callback provided (async check via JavaScript)
        """
        try:
            if not tab:
                if show_warning:
                    self.status_callback("No tab provided.", level="WARNING")
                return False if callback is None else None
            
            # Try to get the browser view
            view = getattr(tab, "browser", None) or getattr(tab, "view", None)
            if view is None:
                if show_warning:
                    self.status_callback("No browser view found.", level="ERROR")
                return False if callback is None else None
            
            # Check basic state
            if view.url().isEmpty() or view.url().toString() == "about:blank":
                if show_warning:
                    self.status_callback("No page loaded.", level="WARNING")
                return False if callback is None else None
            
            # Synchronous check (less reliable but immediate)
            if callback is None:
                return not view.url().isEmpty()
            
            # Async check via JavaScript for accurate ready state
            def check_ready_state(ready_state):
                if ready_state == "complete":
                    callback(view)
                else:
                    if show_warning:
                        self.status_callback(
                            "Page still loading… try again when it finishes.", 
                            level="WARNING"
                        )
            
            view.page().runJavaScript("document.readyState", check_ready_state)
            
        except Exception as e:
            if show_warning:
                self.status_callback(f"Browser check failed: {e}", level="ERROR")
            self._log_error("browser_operations", f"is_browser_ready failed: {e}")
            return False if callback is None else None
    
    def save_screenshot(self, tab=None, save_dir=None, filename_prefix=""):
        """
        Save screenshot of browser view in tab.
        
        Args:
            tab: Tab widget containing browser view
            save_dir: Directory to save to (defaults to settings_manager.config_dir/save)
            filename_prefix: Optional prefix for filename
        
        Returns:
            Path to saved file (via callback), or None on error
        """
        def do_screenshot(view):
            try:
                pixmap = view.grab()
                
                if pixmap.isNull():
                    self.status_callback("Screenshot failed (empty pixmap).", level="ERROR")
                    return
                
                # Determine save directory
                if save_dir is None:
                    if self.settings_manager:
                        target_dir = self.settings_manager.config_dir / "save"
                    else:
                        target_dir = Path.cwd() / "screenshots"
                else:
                    target_dir = Path(save_dir)
                
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filename
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                title = view.title() or view.url().host() or "page"
                safe_title = "".join(
                    ch for ch in title if ch.isalnum() or ch in ("-", "_")
                ).strip() or "page"
                
                if filename_prefix:
                    filename = f"{filename_prefix}_{ts}_{safe_title}.png"
                else:
                    filename = f"{ts}_{safe_title}.png"
                
                target = target_dir / filename
                
                if not pixmap.save(str(target), "PNG"):
                    self.status_callback("Failed to save screenshot.", level="ERROR")
                    return
                
                self.status_callback(f"Saved Screenshot → {target}", level="INFO")
                self._log_system_event("browser_operations", "Screenshot saved", str(target))
                return target
                
            except Exception as e:
                self.status_callback(f"Screenshot failed: {e}", level="ERROR")
                self._log_error("browser_operations", f"Screenshot failed: {e}")
        
        self.is_browser_ready(tab=tab, callback=do_screenshot)
    
    def save_html(self, tab=None, save_dir=None, filename_prefix=""):
        """
        Save HTML content of the current page.
        
        Args:
            tab: Tab widget
            save_dir: Directory to save to
            filename_prefix: Optional prefix for filename
        """
        def do_save_html(view):
            try:
                # Determine save directory
                if save_dir is None:
                    if self.settings_manager:
                        target_dir = self.settings_manager.config_dir / "save"
                    else:
                        target_dir = Path.cwd() / "html_saves"
                else:
                    target_dir = Path(save_dir)
                
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filename
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                title = view.title() or view.url().host() or "page"
                safe_title = "".join(
                    ch for ch in title if ch.isalnum() or ch in ("-", "_")
                ).strip() or "page"
                
                if filename_prefix:
                    filename = f"{filename_prefix}_{ts}_{safe_title}.html"
                else:
                    filename = f"{ts}_{safe_title}.html"
                
                target = target_dir / filename
                
                def write_html(html: str):
                    try:
                        target.write_text(html, encoding="utf-8")
                        self.status_callback(f"Saved HTML → {target}", level="INFO")
                        if self.command_callback:
                            # Mirror to controller "Command Log" if available
                            try:
                                self.command_callback(f"Saved HTML → {target}")
                            except Exception:
                                pass
                        self._log_system_event("browser_operations", "HTML saved", str(target))
                    except Exception as e:
                        self.status_callback(f"Failed to write HTML: {e}", level="ERROR")
                        self._log_error("browser_operations", f"Write HTML failed: {e}")
                
                view.page().toHtml(write_html)
                
            except Exception as e:
                self.status_callback(f"Save HTML failed: {e}", level="ERROR")
                self._log_error("browser_operations", f"Save HTML failed: {e}")
        
        self.is_browser_ready(tab=tab, callback=do_save_html)
    
    def save_full_page_screenshot(self, tab=None, save_dir=None, filename_prefix=""):
        """
        Capture the entire scrollable page to a single PNG (stitched tiles).
        
        Args:
            tab: Tab widget
            save_dir: Directory to save to
            filename_prefix: Optional prefix for filename
        """
        try:
            if not tab:
                self.status_callback("No tab provided.", level="WARNING")
                return
            
            view = getattr(tab, "browser", None) or getattr(tab, "view", None)
            if not view:
                self.status_callback("No browser view found.", level="ERROR")
                return
            
            page = view.page()
            
            # Determine save directory
            if save_dir is None:
                if self.settings_manager:
                    target_dir = self.settings_manager.config_dir / "save"
                else:
                    target_dir = Path.cwd() / "screenshots"
            else:
                target_dir = Path(save_dir)
            
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = view.title() or view.url().host() or "page"
            safe_title = "".join(
                ch for ch in title if ch.isalnum() or ch in ("-", "_")
            ).strip() or "page"
            
            if filename_prefix:
                filename = f"{filename_prefix}_{ts}_{safe_title}_fullpage.png"
            else:
                filename = f"{ts}_{safe_title}_fullpage.png"
            
            target = target_dir / filename
            
            # Disallow re-entry
            if self._fps_busy:
                self.status_callback("Full-page capture already in progress…", level="WARNING")
                return
            
            self._fps_busy = True
            self._fps_target = target
            self._fps_tab = tab
            
            # JavaScript to get page dimensions
            js = """
            (function() {
                try {
                    var e = document.documentElement;
                    var b = document.body;
                    
                    var totalWidth = Math.max(
                        e ? e.scrollWidth || 0 : 0,
                        b ? b.scrollWidth || 0 : 0
                    );
                    var totalHeight = Math.max(
                        e ? e.scrollHeight || 0 : 0,
                        b ? b.scrollHeight || 0 : 0
                    );
                    var viewportWidth = window.innerWidth || 0;
                    var viewportHeight = window.innerHeight || 0;
                    var dpr = window.devicePixelRatio || 1;
                    
                    var result = {
                        totalWidth: totalWidth,
                        totalHeight: totalHeight,
                        viewportWidth: viewportWidth,
                        viewportHeight: viewportHeight,
                        dpr: dpr
                    };
                    
                    return JSON.stringify(result);
                    
                } catch (err) {
                    return JSON.stringify({error: err.toString()});
                }
            })();
            """
            
            self.status_callback("Measuring page for full capture…", level="INFO")
            QTimer.singleShot(1000, lambda: page.runJavaScript(js, self._fps_start))
            
        except Exception as e:
            self._fps_fail(f"Full-page capture failed: {e}")
            self._fps_reset()
    
    def _fps_start(self, metrics_json):
        """Initialize stitching based on JS metrics"""
        try:
            if not metrics_json or metrics_json == '':
                self._fps_fail("JavaScript returned empty result.")
                self._fps_reset()
                return
            
            import json
            try:
                metrics = json.loads(metrics_json)
            except (json.JSONDecodeError, TypeError) as e:
                self._fps_fail(f"Could not parse JavaScript result: {e}")
                self._fps_reset()
                return
            
            if 'error' in metrics:
                self._fps_fail(f"JavaScript error: {metrics['error']}")
                self._fps_reset()
                return
            
            tw = int(metrics.get("totalWidth", 0))
            th = int(metrics.get("totalHeight", 0))
            vw = int(metrics.get("viewportWidth", 0))
            vh = int(metrics.get("viewportHeight", 0))
            dpr = float(metrics.get("dpr", 1.0))
            
            if not (tw and th and vw and vh):
                self._fps_fail("Invalid page metrics.")
                self._fps_reset()
                return
            
            w_px = int(tw * dpr)
            h_px = int(th * dpr)
            self._fps_img = QImage(w_px, h_px, QImage.Format_ARGB32)
            self._fps_img.fill(0)
            self._fps_painter = QPainter(self._fps_img)
            
            cols = (tw + vw - 1) // vw
            rows = (th + vh - 1) // vh
            positions = []
            for r in range(rows):
                for c in range(cols):
                    x = c * vw
                    y = r * vh
                    positions.append((x, y))
            
            self._fps_positions = positions
            self._fps_dpr = dpr
            self._fps_vw = vw
            self._fps_vh = vh
            self._fps_tw = tw
            self._fps_th = th
            
            self.status_callback(
                f"Capturing full page {tw}×{th}px ({len(positions)} tiles)…", 
                level="INFO"
            )
            self._fps_next_tile()
            
        except Exception as e:
            self._fps_fail(f"Init error: {e}")
            self._fps_reset()
    
    def _fps_next_tile(self):
        """Scroll to next tile and schedule a grab"""
        try:
            if not self._fps_positions:
                self._fps_finish()
                return
            
            x, y = self._fps_positions.pop(0)
            total = (self._fps_tw + self._fps_vh - 1) // self._fps_vh * \
                    ((self._fps_tw + self._fps_vw - 1) // self._fps_vw)
            done = total - len(self._fps_positions)
            self.status_callback(f"Capturing tile {done}/{total}…", level="INFO")
            
            view = getattr(self._fps_tab, "browser", None) or getattr(self._fps_tab, "view", None)
            if not view:
                self._fps_fail("Lost browser view reference")
                self._fps_reset()
                return
            
            js_scroll = f"window.scrollTo({x}, {y}); true;"
            page = view.page()
            page.runJavaScript(
                js_scroll, 
                lambda _: QTimer.singleShot(120, lambda: self._fps_grab_tile(x, y))
            )
            
        except Exception as e:
            self._fps_fail(f"Tile error: {e}")
            self._fps_reset()
    
    def _fps_grab_tile(self, x, y):
        """Grab current viewport and paint to stitched image"""
        try:
            view = getattr(self._fps_tab, "browser", None) or getattr(self._fps_tab, "view", None)
            if not view:
                self._fps_fail("Lost browser view reference")
                self._fps_reset()
                return
            
            pm = view.grab()
            if pm.isNull():
                self._fps_fail("Grabbed empty frame.")
                self._fps_reset()
                return
            
            try:
                pm.setDevicePixelRatio(1.0)
            except Exception:
                pass
            
            img = pm.toImage()
            dpr = self._fps_dpr
            tw, th = self._fps_tw, self._fps_th
            
            dest_x = int(x * dpr)
            dest_y = int(y * dpr)
            
            src_w = img.width()
            src_h = img.height()
            
            remain_w = int(tw * dpr) - dest_x
            remain_h = int(th * dpr) - dest_y
            copy_w = min(src_w, remain_w)
            copy_h = min(src_h, remain_h)
            
            if copy_w > 0 and copy_h > 0:
                self._fps_painter.drawImage(
                    QRect(dest_x, dest_y, copy_w, copy_h),
                    img,
                    QRect(0, 0, copy_w, copy_h)
                )
            
            self._fps_next_tile()
            
        except Exception as e:
            self._fps_fail(f"Grab error: {e}")
            self._fps_reset()
    
    def _fps_finish(self):
        """Finalize and save stitched image"""
        try:
            self._fps_painter.end()
            ok = self._fps_img.save(str(self._fps_target), "PNG")
            if not ok:
                self._fps_fail("Failed to save stitched image.")
            else:
                # Scroll back to top after full page capture
                if self._fps_tab and hasattr(self._fps_tab, "view") and self._fps_tab.view:
                    self._fps_tab.view.page().runJavaScript("window.scrollTo(0, 0);")
                self.status_callback(f"Saved Full Page → {self._fps_target}", level="INFO")
                self._log_system_event("browser_operations", "Full page screenshot saved", str(self._fps_target))
        except Exception as e:
            self._fps_fail(f"Save error: {e}")
        finally:
            self._fps_reset()
    def _fps_fail(self, msg: str):
        """Handle full-page screenshot failure"""
        self.status_callback(msg, level="ERROR")
        self._log_error("browser_operations", msg)
    
    def _fps_reset(self):
        """Clean up full-page screenshot state"""
        for attr in ("_fps_img", "_fps_painter", "_fps_positions", "_fps_dpr",
                    "_fps_vw", "_fps_vh", "_fps_tw", "_fps_th", "_fps_target", "_fps_tab"):
            if hasattr(self, attr):
                setattr(self, attr, None)
        self._fps_busy = False
    
    def execute_javascript(self, tab, script, callback=None):
        """
        Execute JavaScript in browser when ready.
        
        Args:
            tab: Tab widget
            script: JavaScript code to execute
            callback: Optional callback for result
        """
        def do_execute(view):
            if callback:
                view.page().runJavaScript(script, callback)
            else:
                view.page().runJavaScript(script)
        
        self.is_browser_ready(tab=tab, callback=do_execute)
    
    def get_page_content(self, tab, callback):        
        """
        Get HTML content of current page.
        
        Args:
            tab: Tab widget
            callback: Function(html_content) to receive the HTML
        """
        def do_get_content(view):
            view.page().toHtml(callback)
        
        self.is_browser_ready(tab=tab, callback=do_get_content)


    def extract_images(self, tab=None, save_dir=None, filename_prefix=""):
        """
        Extract and save all images from the current page.
    
        Args:
            tab: Tab widget
            save_dir: Directory to save to
            filename_prefix: Optional prefix for filename
        """

        def do_extract_images(view):
            try:
                # Determine save directory
                if save_dir is None:
                    if self.settings_manager:
                        target_dir = self.settings_manager.config_dir / "save" / "images"
                    else:
                        target_dir = Path.cwd() / "images"
                else:
                    target_dir = Path(save_dir) / "images"
                
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate base filename
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                host = view.url().host() or "page"
                safe_host = "".join(
                    ch for ch in host if ch.isalnum() or ch in ("-", "_")
                ).strip() or "page"
                
                if filename_prefix:
                    base_filename = f"{filename_prefix}_{ts}_{safe_host}"
                else:
                    base_filename = f"{ts}_{safe_host}"
                
                # JavaScript to get all image URLs from the page
                script = """
                (function() {
                    let images = [];
                    const imgElements = document.querySelectorAll('img');
                    
                    imgElements.forEach((img, index) => {
                        if (img.src) {
                            let src = img.src;
                            // Skip data URLs for efficiency
                            if (!src.startsWith('data:')) {
                                images.push({
                                    index: index,
                                    src: src,
                                    alt: img.alt || '',
                                    width: img.width,
                                    height: img.height
                                });
                            }
                        }
                    });
                    
                    return images;
                })();
                """
                
                # Execute JavaScript to get image URLs
                def process_images(images_data):
                    if not images_data:
                        self.status_callback("No images found on page.", level="WARNING")
                        return
                    
                    # Log info
                    self.status_callback(f"Found {len(images_data)} images on page.", level="INFO")
                    self._log_system_event("browser_operations", f"Extracting {len(images_data)} images", 
                                        f"from {view.url().toString()}")
                    
                    # Create a manifest file for images
                    manifest_path = target_dir / f"{base_filename}_manifest.json"
                    
                    total_saved = 0
                    saved_images = []
                    
                    # Process each image
                    for img in images_data:
                        try:
                            img_url = img['src']
                            if not img_url:
                                continue
                                
                            # Normalize URL (handle relative URLs)
                            if not img_url.startswith(('http://', 'https://')):
                                base_url = view.url().toString()
                                if img_url.startswith('/'):
                                    # Absolute path relative to domain
                                    parts = base_url.split('://', 1)
                                    if len(parts) > 1:
                                        protocol, rest = parts
                                        domain = rest.split('/', 1)[0]
                                        img_url = f"{protocol}://{domain}{img_url}"
                                else:
                                    # Relative path
                                    base_path = '/'.join(base_url.split('/')[:-1]) + '/'
                                    img_url = f"{base_path}{img_url}"
                            
                            # Create a safe filename
                            img_filename = f"{base_filename}_{img['index']:03d}.png"
                            img_path = target_dir / img_filename
                            
                            # Save image info
                            img_info = {
                                'index': img['index'],
                                'original_url': img['src'],
                                'resolved_url': img_url,
                                'alt_text': img['alt'],
                                'width': img['width'],
                                'height': img['height'],
                                'saved_as': img_filename
                            }
                            saved_images.append(img_info)
                            
                            # Download the image using the page's network access
                            download_script = f"""
                            (function() {{
                                return new Promise((resolve, reject) => {{
                                    const img = new Image();
                                    img.crossOrigin = "Anonymous";
                                    img.onload = function() {{
                                        const canvas = document.createElement('canvas');
                                        canvas.width = img.width;
                                        canvas.height = img.height;
                                        const ctx = canvas.getContext('2d');
                                        ctx.drawImage(img, 0, 0);
                                        resolve(canvas.toDataURL('image/png'));
                                    }};
                                    img.onerror = function() {{
                                        reject('Failed to load image');
                                    }};
                                    img.src = "{img_url}";
                                }});
                            }})();
                            """
                            
                            def save_image_data(data_url):
                                nonlocal total_saved
                                try:
                                    if not data_url or not isinstance(data_url, str) or not data_url.startswith('data:image'):
                                        return
                                    
                                    # Extract base64 data
                                    import base64
                                    header, encoded = data_url.split(",", 1)
                                    decoded = base64.b64decode(encoded)
                                    
                                    # Save to file
                                    with open(img_path, 'wb') as f:
                                        f.write(decoded)
                                    
                                    total_saved += 1
                                    self.status_callback(f"Saved image {total_saved}/{len(images_data)}", level="INFO")
                                    
                                    # If all images are processed, write the manifest
                                    if total_saved == len(saved_images):
                                        import json
                                        with open(manifest_path, 'w') as f:
                                            json.dump({
                                                'url': view.url().toString(),
                                                'title': view.title(),
                                                'timestamp': datetime.now().isoformat(),
                                                'total_images': len(saved_images),
                                                'images': saved_images
                                            }, f, indent=2)
                                        
                                        self.status_callback(f"Saved {total_saved} images to {target_dir}", level="INFO")
                                        self._log_system_event("browser_operations", "Images extracted", 
                                                            f"Saved {total_saved} images to {target_dir}")
                                except Exception as e:
                                    self.status_callback(f"Error saving image: {e}", level="ERROR")
                            
                            # Execute the download script for each image
                            view.page().runJavaScript(download_script, save_image_data)
                            
                        except Exception as e:
                            self.status_callback(f"Error processing image {img['index']}: {e}", level="ERROR")
                    
                    # If no images were processed, show a message
                    if not saved_images:
                        self.status_callback("No valid images found to extract.", level="WARNING")
                
                # Execute the script to get image URLs
                view.page().runJavaScript(script, process_images)
                
            except Exception as e:
                self.status_callback(f"Image extraction failed: {e}", level="ERROR")
                self._log_error("browser_operations", f"Image extraction failed: {e}")
        
        self.is_browser_ready(tab=tab, callback=do_extract_images)
import customtkinter as ctk
from customtkinter import filedialog
from PIL import Image, ImageDraw
import pygame
import os
from threading import Thread


class GMOUI:
    """
    GMO Audio Security System UI
    
    This class encapsulates all UI logic for the GMO system.
    Can be imported and triggered by other modules.
    
    Usage:
        gmo = GMOUI()
        gmo.show()  # Display the dashboard
        gmo.force_trigger()  # Pop up the incoming call notification
    """
    
    def __init__(self):
        """Initialize the GMO UI and state"""
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # State variables
        self.state = {
            "selected_mp3_path": "decoy.mp3",
            "ringtone_path": "assets/ringtone.mp3",
            "caller_image_path": "assets/caller.png",
            "gmo_active": False,
            "mic_active": False,
            "ringtone_playing": False
        }
        
        # Cute Pink & Green Color Scheme
        self.BG_COLOR = "#FFB3E6"
        self.CARD_COLOR = "#FFD9F0"
        self.ACCENT_GREEN1 = "#A8E6B8"
        self.ACCENT_GREEN2 = "#6FD98E"
        self.ACCENT_RED = "#FF6B9D"
        self.TEXT_PRIMARY = "#FFFFFF"
        self.TEXT_SECONDARY = "#7B4A8A"
        self.SHADOW_COLOR = "#E085C0"
        
        # Create the main window
        self.app = ctk.CTk()
        self.app.title("GMO - Audio Security")
        self.app.geometry("600x800")
        self.app.attributes('-topmost', False)
        self.app.configure(fg_color=self.BG_COLOR)
        
        # Store references for UI updates
        self.mic_status_dot = None
        self.mic_status_text = None
        self.ringtone_thread = None
        self.logo_image = None
        self.caller_image_cache = None  # ← ADD THIS
    
    def _load_logo(self, logo_path="assets/logo.png", width=60, height=60):
        """
        Load and resize a PNG logo for display.
        
        Args:
            logo_path (str): Path to the PNG logo file
            width (int): Desired width in pixels
            height (int): Desired height in pixels
            
        Returns:
            ctk.CTkImage or None: The loaded image, or None if file not found
        """
        try:
            if os.path.exists(logo_path):
                # Load the image
                image = Image.open(logo_path)
                
                # Convert RGBA to RGB if necessary (for compatibility)
                if image.mode == 'RGBA':
                    pass
                elif image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Resize the image
                image = image.resize((width, height), Image.Resampling.LANCZOS)
                
                # Convert to CTkImage
                self.logo_image = ctk.CTkImage(light_image=image, size=(width, height))
                return self.logo_image
            else:
                print(f"Logo file not found at {logo_path}. Using text instead.")
                return None
        except Exception as e:
            print(f"Error loading logo: {str(e)}")
            return None
    
    def _load_caller_image(self, image_path="assets/caller.png", width=60, height=60):
        """
        Load and resize a PNG image for the incoming call avatar.
        Improved version with better error handling and caching.
        
        Args:
            image_path (str): Path to the PNG image file
            width (int): Desired width in pixels
            height (int): Desired height in pixels
            
        Returns:
            ctk.CTkImage or None: The loaded image, or None if file not found
        """
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                print(f"❌ Caller image not found at: {image_path}")
                print(f"   Current working directory: {os.getcwd()}")
                print(f"   Please ensure 'assets/caller.png' exists")
                return None
            
            print(f"✅ Found caller image at: {image_path}")
            
            # Load the image
            image = Image.open(image_path)
            print(f"✅ Image loaded. Size: {image.size}, Mode: {image.mode}")
            
            # Convert to RGB if necessary
            if image.mode == 'RGBA':
                # Create a white background and paste the image with alpha
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
                print(f"✅ Converted RGBA to RGB with white background")
            elif image.mode != 'RGB':
                image = image.convert('RGB')
                print(f"✅ Converted {image.mode} to RGB")
            
            # Resize the image maintaining aspect ratio
            original_size = image.size
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            print(f"✅ Resized from {original_size} to {image.size}")
            
            # Create a new image with the desired size and paste the resized image in the center
            final_image = Image.new('RGB', (width, height), (255, 255, 255))
            offset = ((width - image.width) // 2, (height - image.height) // 2)
            final_image.paste(image, offset)
            print(f"✅ Centered image in {width}x{height} canvas")
            
            # Convert to CTkImage
            caller_image = ctk.CTkImage(light_image=final_image, size=(width, height))
            print(f"✅ Created CTkImage successfully")
            
            # Cache the image to prevent garbage collection
            self.caller_image_cache = caller_image
            
            return caller_image
            
        except Exception as e:
            print(f"❌ Error loading caller image: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def show(self):
        """Display the dashboard screen"""
        self.show_dashboard()
        self.app.mainloop()
    
    def _play_ringtone_loop(self):
        """
        Play the ringtone file in a loop until the call is accepted or declined.
        Runs in a separate thread.
        """
        try:
            pygame.mixer.music.load(self.state["ringtone_path"])
            self.state["ringtone_playing"] = True
            
            pygame.mixer.music.play(-1)
            
            while self.state["ringtone_playing"]:
                pygame.time.delay(100)
            
            pygame.mixer.music.stop()
            
        except FileNotFoundError:
            print(f"Error: Could not find ringtone file at {self.state['ringtone_path']}")
        except Exception as e:
            print(f"Error playing ringtone: {str(e)}")
    
    def _start_ringtone(self):
        """Start playing the ringtone in a background thread"""
        if self.ringtone_thread and self.ringtone_thread.is_alive():
            self.state["ringtone_playing"] = False
            self.ringtone_thread.join(timeout=1)
        
        self.state["ringtone_playing"] = True
        self.ringtone_thread = Thread(target=self._play_ringtone_loop, daemon=True)
        self.ringtone_thread.start()
    
    def _stop_ringtone(self):
        """Stop playing the ringtone"""
        self.state["ringtone_playing"] = False
        pygame.mixer.music.stop()
        if self.ringtone_thread and self.ringtone_thread.is_alive():
            self.ringtone_thread.join(timeout=1)
    
    def force_trigger(self):
        """
        Force the GMO window to pop up and show the incoming call.
        """
        self.app.deiconify()
        self.app.attributes('-topmost', True)
        self.app.update()
        self.state["mic_active"] = True
        self.show_incoming_call()
    
    def show_dashboard(self):
        """Display the setup/dashboard screen"""
        self._stop_ringtone()
        self.state["gmo_active"] = False
        self.state["mic_active"] = False
        
        for widget in self.app.winfo_children():
            widget.destroy()
        
        self.app.geometry("600x800")
        self.app.attributes('-topmost', False)
        
        main_frame = ctk.CTkFrame(self.app, fg_color=self.BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # TOP STATUS BAR
        shadow_bar = ctk.CTkFrame(main_frame, fg_color=self.SHADOW_COLOR, corner_radius=16)
        shadow_bar.pack(fill="x", pady=(0, 25), padx=3)
        
        status_bar = ctk.CTkFrame(shadow_bar, fg_color=self.CARD_COLOR, corner_radius=14)
        status_bar.pack(fill="x", padx=3, pady=3)
        
        mic_indicator_frame = ctk.CTkFrame(status_bar, fg_color=self.CARD_COLOR)
        mic_indicator_frame.pack(side="left", padx=20, pady=18)
        
        self.mic_status_dot = ctk.CTkLabel(
            mic_indicator_frame,
            text="●",
            font=("Arial", 24),
            text_color=self.ACCENT_RED
        )
        self.mic_status_dot.pack(side="left", padx=(0, 12))
        
        self.mic_status_text = ctk.CTkLabel(
            mic_indicator_frame,
            text="Mic: OFF",
            font=("Comic Sans MS", 13, "bold"),
            text_color=self.TEXT_SECONDARY
        )
        self.mic_status_text.pack(side="left")
        
        # HEADER
        header_frame = ctk.CTkFrame(main_frame, fg_color=self.BG_COLOR)
        header_frame.pack(fill="x", pady=(0, 35))
        
        logo = self._load_logo("assets/logo.png", width=70, height=70)
        if logo:
            logo_label = ctk.CTkLabel(header_frame, image=logo, text="")
            logo_label.pack(side="left", padx=(0, 15))
        
        title_container = ctk.CTkFrame(header_frame, fg_color=self.BG_COLOR)
        title_container.pack(side="left", fill="both", expand=True)
        
        title_label = ctk.CTkLabel(
            title_container,
            text="GMO",
            font=("Comic Sans MS", 48, "bold"),
            text_color=self.TEXT_PRIMARY
        )
        title_label.pack(anchor="w", padx=5)
        
        subtitle_label = ctk.CTkLabel(
            title_container,
            text="Get Me Out - Audio Security",
            font=("Comic Sans MS", 15),
            text_color=self.TEXT_SECONDARY
        )
        subtitle_label.pack(anchor="w", pady=(8, 0), padx=5)
        
        # INSTRUCTIONS
        shadow_instructions = ctk.CTkFrame(main_frame, fg_color=self.SHADOW_COLOR, corner_radius=18)
        shadow_instructions.pack(fill="x", pady=(0, 20), padx=3)
        
        instructions_frame = ctk.CTkFrame(shadow_instructions, fg_color=self.CARD_COLOR, corner_radius=16)
        instructions_frame.pack(fill="x", padx=3, pady=3)
        
        instructions_title = ctk.CTkLabel(
            instructions_frame,
            text="📋 Setup Instructions",
            font=("Comic Sans MS", 17, "bold"),
            text_color=self.TEXT_PRIMARY
        )
        instructions_title.pack(anchor="w", padx=20, pady=(18, 12))
        
        instructions_text = ctk.CTkLabel(
            instructions_frame,
            text="1. Select your decoy MP3 file\n2. Click 'Get Me Out' to activate\n3. The system will monitor and play audio when triggered",
            font=("Comic Sans MS", 13),
            text_color=self.TEXT_SECONDARY,
            justify="left"
        )
        instructions_text.pack(anchor="nw", padx=20, pady=(0, 18))
        
        # FILE SELECTION
        shadow_file = ctk.CTkFrame(main_frame, fg_color=self.SHADOW_COLOR, corner_radius=18)
        shadow_file.pack(fill="x", pady=(0, 20), padx=3)
        
        file_frame = ctk.CTkFrame(shadow_file, fg_color=self.CARD_COLOR, corner_radius=16)
        file_frame.pack(fill="x", padx=3, pady=3)
        
        file_label = ctk.CTkLabel(
            file_frame,
            text="🎵 Selected Audio File",
            font=("Comic Sans MS", 15, "bold"),
            text_color=self.TEXT_PRIMARY
        )
        file_label.pack(anchor="w", padx=20, pady=(18, 12))
        
        file_display_label = ctk.CTkLabel(
            file_frame,
            text=f"📁 {os.path.basename(self.state['selected_mp3_path'])}",
            font=("Comic Sans MS", 12),
            text_color=self.ACCENT_GREEN2
        )
        file_display_label.pack(anchor="w", padx=20, pady=(0, 12))
        
        def pick_file():
            file_path = filedialog.askopenfilename(
                filetypes=[("Audio Files", "*.mp3"), ("All Files", "*.*")],
                title="Select MP3 File"
            )
            if file_path:
                self.state["selected_mp3_path"] = file_path
                file_display_label.configure(text=f"📁 {os.path.basename(file_path)}")
        
        pick_button = ctk.CTkButton(
            file_frame,
            text="📂 Browse Files",
            width=200,
            height=42,
            corner_radius=10,
            fg_color=self.ACCENT_GREEN1,
            hover_color=self.ACCENT_GREEN2,
            text_color=self.TEXT_PRIMARY,
            font=("Comic Sans MS", 13, "bold"),
            command=pick_file
        )
        pick_button.pack(anchor="w", padx=20, pady=(0, 18))
        
        # STATUS
        shadow_status = ctk.CTkFrame(main_frame, fg_color=self.SHADOW_COLOR, corner_radius=18)
        shadow_status.pack(fill="x", pady=(0, 35), padx=3)
        
        status_frame = ctk.CTkFrame(shadow_status, fg_color=self.CARD_COLOR, corner_radius=16)
        status_frame.pack(fill="x", padx=3, pady=3)
        
        status_label = ctk.CTkLabel(
            status_frame,
            text="✅ Status: Ready",
            font=("Comic Sans MS", 13),
            text_color=self.TEXT_SECONDARY
        )
        status_label.pack(anchor="w", padx=20, pady=16)
        
        # BUTTON
        shadow_button = ctk.CTkFrame(main_frame, fg_color=self.SHADOW_COLOR, corner_radius=16)
        shadow_button.pack(fill="x", padx=3, pady=3)
        
        start_button = ctk.CTkButton(
            shadow_button,
            text="💨 Get Me Out",
            width=300,
            height=55,
            corner_radius=14,
            fg_color=self.ACCENT_GREEN2,
            hover_color=self.ACCENT_GREEN1,
            text_color=self.TEXT_PRIMARY,
            font=("Comic Sans MS", 18, "bold"),
            command=self._start_gmo
        )
        start_button.pack(fill="x", padx=3, pady=3)
    
    def _start_gmo(self):
        """Internal method to start GMO and show incoming call"""
        self.state["mic_active"] = True
        self.show_incoming_call()
    
    def show_incoming_call(self):
        """Display the incoming call notification"""
        self.state["gmo_active"] = True
        self._start_ringtone()
        
        for widget in self.app.winfo_children():
            widget.destroy()
        
        main_frame = ctk.CTkFrame(self.app, fg_color=self.BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        self.app.geometry("650x130")
        screen_width = self.app.winfo_screenwidth()
        screen_height = self.app.winfo_screenheight()
        x = (screen_width - 650) // 2
        y = 100
        self.app.geometry(f"650x130+{x}+{y}")
        
        shadow_notification = ctk.CTkFrame(main_frame, fg_color=self.SHADOW_COLOR, corner_radius=20)
        shadow_notification.pack(fill="both", expand=True, padx=8, pady=8)
        
        notification_frame = ctk.CTkFrame(shadow_notification, fg_color=self.CARD_COLOR, corner_radius=18)
        notification_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        def play_audio():
            try:
                self._stop_ringtone()
                pygame.mixer.music.load(self.state["selected_mp3_path"])
                pygame.mixer.music.play()
                accept_button.configure(state="disabled")
                status_label.configure(text="Call Connected ✓")
            except FileNotFoundError:
                status_label.configure(text="Error: File not found!")
            except Exception as e:
                status_label.configure(text=f"Error: {str(e)}")
        
        def decline_call():
            self._stop_ringtone()
            self.state["mic_active"] = False
            self.show_dashboard()
        
        left_frame = ctk.CTkFrame(notification_frame, fg_color=self.CARD_COLOR)
        left_frame.pack(side="left", fill="both", expand=True, padx=18, pady=18)
        
        # LOAD CALLER IMAGE
        print("\n" + "="*50)
        print("Loading caller image...")
        print("="*50)
        caller_image = self._load_caller_image(self.state["caller_image_path"], width=60, height=60)
        print("="*50 + "\n")
        
        if caller_image:
            print("✅ Using custom caller image")
            avatar_label = ctk.CTkLabel(left_frame, image=caller_image, text="")
        else:
            print("❌ Custom image not loaded, using default avatar")
            # Default avatar
            def create_avatar(size=60, initial="H", bg_color=None):
                if bg_color is None:
                    bg_color = self.ACCENT_GREEN2
                img = Image.new('RGB', (size, size), color=bg_color)
                draw = ImageDraw.Draw(img)
                try:
                    from PIL import ImageFont
                    font = ImageFont.load_default()
                    text_bbox = draw.textbbox((0, 0), initial, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    text_x = (size - text_width) // 2
                    text_y = (size - text_height) // 2
                    draw.text((text_x, text_y), initial, fill='#ffffff', font=font)
                except:
                    pass
                return ctk.CTkImage(light_image=img, size=(size, size))
            
            avatar_image = create_avatar(size=60, initial="H", bg_color=self.ACCENT_GREEN2)
            avatar_label = ctk.CTkLabel(left_frame, image=avatar_image, text="")
        
        avatar_label.pack(side="left", padx=(0, 18))
        
        text_frame = ctk.CTkFrame(left_frame, fg_color=self.CARD_COLOR)
        text_frame.pack(side="left", fill="both", expand=True)
        
        caller_name = ctk.CTkLabel(
            text_frame,
            text="Home Phone",
            font=("Comic Sans MS", 16, "bold"),
            text_color=self.TEXT_PRIMARY
        )
        caller_name.pack(anchor="w", padx=3)
        
        caller_label = ctk.CTkLabel(
            text_frame,
            text="home",
            font=("Comic Sans MS", 13),
            text_color=self.TEXT_SECONDARY
        )
        caller_label.pack(anchor="w", padx=3, pady=(2, 0))
        
        status_label = ctk.CTkLabel(
            text_frame,
            text="",
            font=("Comic Sans MS", 11),
            text_color=self.ACCENT_GREEN2
        )
        status_label.pack(anchor="w", padx=3)
        
        right_frame = ctk.CTkFrame(notification_frame, fg_color=self.CARD_COLOR)
        right_frame.pack(side="right", fill="both", padx=18, pady=12)
        
        accept_button = ctk.CTkButton(
            right_frame,
            text="✓ Accept",
            width=100,
            height=38,
            corner_radius=10,
            fg_color=self.ACCENT_GREEN2,
            hover_color=self.ACCENT_GREEN1,
            text_color=self.TEXT_PRIMARY,
            font=("Comic Sans MS", 13, "bold"),
            command=play_audio
        )
        accept_button.pack(pady=(0, 8))
        
        decline_button = ctk.CTkButton(
            right_frame,
            text="✕ Decline",
            width=100,
            height=38,
            corner_radius=10,
            fg_color=self.ACCENT_RED,
            hover_color="#FF4A7F",
            text_color=self.TEXT_PRIMARY,
            font=("Comic Sans MS", 13, "bold"),
            command=decline_call
        )
        decline_button.pack()
    
    def set_audio_path(self, path):
        """Set the audio file path from external code."""
        if os.path.exists(path):
            self.state["selected_mp3_path"] = path
            return True
        else:
            print(f"Error: File not found at {path}")
            return False
    
    def set_ringtone_path(self, path):
        """Set the ringtone file path from external code."""
        if os.path.exists(path):
            self.state["ringtone_path"] = path
            return True
        else:
            print(f"Error: Ringtone file not found at {path}")
            return False
    
    def set_caller_image_path(self, path):
        """Set the caller image path from external code."""
        if os.path.exists(path):
            self.state["caller_image_path"] = path
            return True
        else:
            print(f"Error: Caller image file not found at {path}")
            return False
    
    def get_state(self):
        """Get the current state of the GMO system."""
        return self.state.copy()


# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    gmo = GMOUI()
    gmo.show()
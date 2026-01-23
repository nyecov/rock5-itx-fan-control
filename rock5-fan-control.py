#!/usr/bin/env python3
import time
import os
import signal
import sys
import glob
import select
import threading

# Configuration
THERMAL_ZONE = "/sys/class/thermal/thermal_zone0"
COOLING_DEV_FALLBACK = "/sys/class/thermal/cooling_device5/cur_state"
PWM_NODE_ADDR = "febf0020" # PWM14/15
RPM_GPIO = 139 # GPIO4_B3 (Pin 139)
POLL_INTERVAL = 3  # Seconds

class RPMReader:
    def __init__(self):
        self.gpio_path = f"/sys/class/gpio/gpio{RPM_GPIO}"
        self.value_path = os.path.join(self.gpio_path, "value")
        self.running = True
        self.rpm = 0
        self.pulse_count = 0
        self.last_time = time.time()
        self.lock = threading.Lock()
        
        self.setup_gpio()
        
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def setup_gpio(self):
        if not os.path.exists(self.gpio_path):
            try:
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(RPM_GPIO))
                time.sleep(0.5)
            except OSError: pass # Already exported
            
        try:
            with open(os.path.join(self.gpio_path, "direction"), "w") as f:
                f.write("in")
            with open(os.path.join(self.gpio_path, "edge"), "w") as f:
                f.write("falling") # Count falling edges (1 pulse per cycle usually, depend on fan)
        except Exception as e:
            print(f"Error setting up RPM GPIO: {e}")

    def _monitor_loop(self):
        try:
            epoll = select.epoll()
            f = open(self.value_path, 'r')
            epoll.register(f, select.EPOLLPRI | select.EPOLLERR)
            
            while self.running:
                events = epoll.poll(1) # 1 second timeout
                if events:
                    f.seek(0)
                    f.read() # Clear interrupt
                    with self.lock:
                        self.pulse_count += 1
                
                # Calculate RPM every so often or let get_rpm do it?
                # Let's simple count here.
        except Exception as e:
            print(f"RPM monitor stopped: {e}")

    def get_rpm(self):
        with self.lock:
            current_time = time.time()
            dt = current_time - self.last_time
            count = self.pulse_count
            
            # Reset
            self.pulse_count = 0
            self.last_time = current_time
            
        if dt == 0: return 0
        
        # RPM = (Pulses / 2) * (60 / dt)
        # Assuming 2 pulses per revolution
        rpm = (count / 2.0) * (60.0 / dt)
        return int(rpm)

class FanController:
    def __init__(self):
        self.release_kernel_driver()
        self.pwm_path = self.find_pwm_chip()
        self.period = 40000 # 25kHz
        self.init_pwm()

    def release_kernel_driver(self):
        # Unbind generic pwm-fan driver if it's holding the device
        driver_path = "/sys/bus/platform/drivers/pwm-fan"
        if os.path.exists(driver_path):
            try:
                # Find devices bound to this driver
                for link in os.listdir(driver_path):
                    if os.path.islink(os.path.join(driver_path, link)):
                        print(f"Unbinding generic fan driver for {link}...")
                        with open(os.path.join(driver_path, "unbind"), "w") as f:
                            f.write(link)
            except Exception as e:
                print(f"Note: Could not unbind pwm-fan driver: {e}")

    def find_pwm_chip(self):
        # Look for the pwmchip that corresponds to our address
        chips = glob.glob("/sys/class/pwm/pwmchip*")
        for chip in chips:
            try:
                # Check device tree node path
                device_link = os.path.join(chip, "device/of_node")
                if os.path.exists(device_link):
                    real_path = os.path.realpath(device_link)
                    if PWM_NODE_ADDR in real_path:
                        print(f"Found PWM chip for {PWM_NODE_ADDR}: {chip}")
                        return chip
            except Exception as e:
                pass
        print(f"PWM chip for {PWM_NODE_ADDR} not found, using valid thermal fallback if available.")
        return None

    def init_pwm(self):
        if not self.pwm_path:
            return
        
        pwm0 = os.path.join(self.pwm_path, "pwm0")
        if not os.path.exists(pwm0):
            try:
                with open(os.path.join(self.pwm_path, "export"), "w") as f:
                    f.write("0")
                time.sleep(0.5) 
            except OSError: 
                pass # Already exported

        # 1. Disable first to allow config changes
        try:
            with open(os.path.join(pwm0, "enable"), "w") as f:
                f.write("0")
        except: pass

        # 2. Set Period
        try:
            with open(os.path.join(pwm0, "period"), "w") as f:
                f.write(str(self.period))
        except Exception as e:
            print(f"Warning: Could not set period: {e}")

        # 3. Try Polarity (don't crash if fails)
        try:
            with open(os.path.join(pwm0, "polarity"), "w") as f:
                f.write("normal")
        except: 
            print("Note: Could not set polarity to normal (likely locked). Procceeding.")

        # 4. Enable! (Critical)
        try:
            with open(os.path.join(pwm0, "enable"), "w") as f:
                f.write("1")
        except Exception as e:
            print(f"Error enabling PWM: {e}")

    def set_speed(self, speed_level):
        # Speed level 0-4
        if self.pwm_path:
            # Direct PWM Control
            # Map 0-4 to 0-100% duty cycle
            duty_cycle = int(self.period * (speed_level / 4.0))
            # Ensure 0 is 0
            if speed_level == 0: duty_cycle = 0
            
            try:
                with open(os.path.join(self.pwm_path, "pwm0/duty_cycle"), "w") as f:
                    f.write(str(duty_cycle))
            except Exception as e:
                print(f"Error setting PWM duty: {e}")
        else:
            try:
                with open(COOLING_DEV_FALLBACK, "w") as f:
                    f.write(str(speed_level))
            except Exception as e:
                print(f"Error setting cooling device: {e}")

    def run_self_test(self, rpm_reader=None):
        print("--- Starting Fan Speed Self-Test (10s per level) ---")
        for level in range(5):
            print(f"Test Mode: Setting Speed Level {level} (Duration: 10s)")
            self.set_speed(level)
            # Sleep 10s but log RPM every 2 seconds
            for i in range(5):
                time.sleep(2)
                if rpm_reader:
                    print(f"  [Level {level}] RPM: {rpm_reader.get_rpm()}")
        print("--- Self-Test Complete. Handing over to thermal policy. ---")

def read_temp():
    try:
        with open(os.path.join(THERMAL_ZONE, "temp"), "r") as f:
            return int(f.read().strip()) / 1000.0
    except Exception as e:
        print(f"Error reading temp: {e}")
        return 75.0 # Fail safe

def get_target_speed(temp):
    if temp <= 40: return 1
    elif temp <= 50: return 2
    elif temp <= 60: return 3
    else: return 4

def set_policy_user_space():
    policy_path = os.path.join(THERMAL_ZONE, "policy")
    try:
        if os.path.exists(policy_path):
            with open(policy_path, "r") as f:
                current = f.read().strip()
            if current != "user_space":
                with open(policy_path, "w") as f:
                    f.write("user_space")
    except: pass



def main():
    print("Starting Rock 5 ITX Fan Control")
    set_policy_user_space()
    
    controller = FanController()
    rpm_reader = RPMReader()
    
    # Run startup test
    controller.run_self_test(rpm_reader)
    
    # If run with --test flag, exit now
    if "--test" in sys.argv:
        print("Test complete. Resetting fan to current thermal target...")
        temp = read_temp()
        target_speed = get_target_speed(temp)
        print(f"Current Temp: {temp:.1f}C -> Restoring Fan Speed: {target_speed}")
        controller.set_speed(target_speed)
        return

    current_speed = -1
    last_rpm = -1
    
    while True:
        set_policy_user_space()
        temp = read_temp()
        target_speed = get_target_speed(temp)
        rpm = rpm_reader.get_rpm()
        
        # Log if speed changed OR significant RPM change
        if (target_speed != current_speed) or (abs(rpm - last_rpm) > 100):
            print(f"Temp: {temp:.1f}C -> Fan Speed: {target_speed} (RPM: {rpm})")
            
            if target_speed != current_speed:
                controller.set_speed(target_speed)
                current_speed = target_speed
                
            last_rpm = rpm
            
        time.sleep(POLL_INTERVAL)

def signal_handler(sig, frame):
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main()

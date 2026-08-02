# Plan for extending pc_control module with deep-OS-settings capabilities

## Files to Modify

### 1. Interface Definition
- `backend/modules/pc_control/ports/pc_control_port.py` - Add new abstract methods

### 2. Type Definitions
- `backend/modules/pc_control/_types.py` - Add new Pydantic/dataclass types

### 3. Exceptions
- `backend/modules/pc_control/_exceptions.py` - Add new exception subclasses

### 4. New Component Files (thin delegators)
- `backend/modules/pc_control/_system_settings.py`
- `backend/modules/pc_control/_software_manager.py`  
- `backend/modules/pc_control/_account_manager.py`

### 5. Adapter Implementations
- `backend/modules/pc_control/_local_adapter.py` - Add stub implementations raising PCControlNotImplementedError
- `backend/modules/pc_control/_production_adapter.py` - Add real implementations

### 6. Module Integration
- `backend/modules/pc_control/pc_control_module.py` - Wire up new components and expose public API

### 7. Security Policy Updates
- `config/security_policy.json` - Add rules for new operations

### 8. Documentation Updates
- `docs/07_Module_Design.md` - Document new capabilities
- `docs/21_System_Contracts.md` - Update tool contracts
- `docs/16_Changelog.md` - Add entry for this feature

### 9. Unit Tests
- `testing/unit/modules/pc_control/test_pc_control_module.py` - Add tests for new functionality
- `testing/unit/modules/pc_control/test_production_adapter.py` - Add tests for adapter implementations

## Detailed Implementation Plan

### Phase 1: Define Interfaces and Types
1. Add new abstract methods to PCControlPort in pc_control_port.py
2. Add new data types to _types.py
3. Add new exception classes to _exceptions.py

### Phase 2: Create Component Classes
1. Create _system_settings.py with SystemSettings class
2. Create _software_manager.py with SoftwareManager class  
3. Create _account_manager.py with AccountManager class

### Phase 3: Implement Adapters
1. Add stub implementations in _local_adapter.py that raise PCControlNotImplementedError
2. Implement real functionality in _production_adapter.py with OS-specific logic

### Phase 4: Integrate into Module
1. Import and instantiate new components in PCControlManager.__init__
2. Add public API methods to PCControlManager
3. Update tool registration in _register_tools method

### Phase 5: Security Configuration
1. Add appropriate rules to security_policy.json for new operations

### Phase 6: Testing
1. Add unit tests for new functionality
2. Ensure existing tests still pass

## Capability Groups Details

### 1. System Settings Toggles
- Wi-Fi control (on/off, list/connect)
- Bluetooth control (on/off, list/pair)
- Display brightness (get/set)
- Display resolution (get/set/list)
- Night light/dark mode toggle
- Airplane mode toggle
- Do Not Disturb/Focus mode toggle

### 2. Software Management
- List installed applications/packages
- Install package (platform-specific)
- Uninstall package
- Check for updates

### 3. User Account Management
- List local user accounts
- Get current logged-in user info
- Create standard local user account
- Enable/disable user account
- Change user group membership (admin/sudo/wheel)

## Implementation Approach

Following the existing patterns in the module:
- Each capability group gets its own component file (_*.py)
- Components take PCControlPort in constructor and delegate to it
- Port interface defines async methods that components call
- Local adapter raises NotImplementedError for all new methods
- Production adapter implements OS-specific logic using subprocess calls to native tools
- All admin-privileged operations go through security checks (following existing patterns)
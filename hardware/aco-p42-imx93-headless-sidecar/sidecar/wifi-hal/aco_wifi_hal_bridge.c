/*
 * Minimal Android 12 legacy Wi-Fi HAL bridge for the FRDM-i.MX93 sidecar.
 *
 * The Android 12 Wi-Fi HAL loader fills the function table with
 * WIFI_ERROR_NOT_SUPPORTED stubs before calling this initializer.  This
 * bridge replaces only the lifecycle and netdev-discovery operations needed
 * to expose the board's already-loaded IW612 interfaces to the framework.
 * Advanced vendor commands remain on the loader's explicit stubs.
 *
 * This is not an Aco protocol or license shim.  The Aco AAR still runs inside
 * the onboard Android sidecar and consumes the platform WifiP2pManager API.
 */

#include <fcntl.h>
#include <stddef.h>
#include <string.h>
#include <unistd.h>

#include <hardware_legacy/wifi_hal.h>

struct bridge_iface {
    char name[IFNAMSIZ];
};

struct bridge_state {
    int stop_pipe[2];
    int iface_count;
    struct bridge_iface iface_storage[3];
    wifi_interface_handle ifaces[3];
};

static struct bridge_state g_state;

static int netdev_exists(const char *name) {
    char path[64] = "/sys/class/net/";
    const size_t base_len = strlen(path);
    const size_t name_len = strlen(name);

    if (base_len + name_len + 1 > sizeof(path)) return 0;
    memcpy(path + base_len, name, name_len + 1);
    return access(path, F_OK) == 0;
}

static void add_iface(struct bridge_state *state, const char *name) {
    struct bridge_iface *iface;
    size_t len;

    if (state->iface_count >= 3 || !netdev_exists(name)) return;
    iface = &state->iface_storage[state->iface_count];
    len = strlen(name);
    if (len >= sizeof(iface->name)) len = sizeof(iface->name) - 1;
    memcpy(iface->name, name, len);
    iface->name[len] = '\0';
    state->ifaces[state->iface_count] = (wifi_interface_handle)iface;
    state->iface_count++;
}

static wifi_error bridge_wait_for_driver_ready(void) {
    int remaining = 200;
    while (remaining-- > 0) {
        if (netdev_exists("wlan0") || netdev_exists("mlan0")) {
            return WIFI_SUCCESS;
        }
        usleep(100000);
    }
    return WIFI_ERROR_TIMED_OUT;
}

static wifi_error bridge_initialize(wifi_handle *handle) {
    if (handle == NULL) return WIFI_ERROR_INVALID_ARGS;

    memset(&g_state, 0, sizeof(g_state));
    g_state.stop_pipe[0] = -1;
    g_state.stop_pipe[1] = -1;
    if (pipe(g_state.stop_pipe) != 0) return WIFI_ERROR_UNKNOWN;

    /* Android-style names first; old Linux names aid diagnostics only. */
    add_iface(&g_state, "wlan0");
    add_iface(&g_state, "p2p0");
    add_iface(&g_state, "wlan1");
    if (g_state.iface_count == 0) {
        add_iface(&g_state, "mlan0");
        add_iface(&g_state, "wfd0");
        add_iface(&g_state, "uap0");
    }
    if (g_state.iface_count == 0) {
        close(g_state.stop_pipe[0]);
        close(g_state.stop_pipe[1]);
        return WIFI_ERROR_NOT_AVAILABLE;
    }

    *handle = (wifi_handle)&g_state;
    return WIFI_SUCCESS;
}

static void bridge_event_loop(wifi_handle handle) {
    struct bridge_state *state = (struct bridge_state *)handle;
    char byte;
    if (state == NULL || state->stop_pipe[0] < 0) return;
    while (read(state->stop_pipe[0], &byte, 1) < 0) {
    }
}

static void bridge_cleanup(wifi_handle handle,
                           wifi_cleaned_up_handler handler) {
    struct bridge_state *state = (struct bridge_state *)handle;
    char byte = 1;
    if (state != NULL && state->stop_pipe[1] >= 0) {
        ssize_t unused = write(state->stop_pipe[1], &byte, 1);
        (void)unused;
    }
    if (handler != NULL) handler(handle);
}

static wifi_error bridge_get_ifaces(wifi_handle handle, int *num,
                                    wifi_interface_handle **ifaces) {
    struct bridge_state *state = (struct bridge_state *)handle;
    if (state == NULL || num == NULL || ifaces == NULL) {
        return WIFI_ERROR_INVALID_ARGS;
    }
    *num = state->iface_count;
    *ifaces = state->ifaces;
    return WIFI_SUCCESS;
}

static wifi_error bridge_get_iface_name(wifi_interface_handle handle,
                                        char *name, size_t size) {
    struct bridge_iface *iface = (struct bridge_iface *)handle;
    size_t len;
    if (iface == NULL || name == NULL || size == 0) {
        return WIFI_ERROR_INVALID_ARGS;
    }
    len = strlen(iface->name);
    if (len + 1 > size) return WIFI_ERROR_INVALID_ARGS;
    memcpy(name, iface->name, len + 1);
    return WIFI_SUCCESS;
}

static wifi_error bridge_get_features(wifi_interface_handle handle,
                                      feature_set *set) {
    (void)handle;
    if (set == NULL) return WIFI_ERROR_INVALID_ARGS;
    /* IW612 exposes a real 5 GHz band in nl80211; report it truthfully. */
    *set = WIFI_FEATURE_INFRA | WIFI_FEATURE_INFRA_5G | WIFI_FEATURE_P2P;
    return WIFI_SUCCESS;
}

static wifi_error bridge_get_chip_features(wifi_handle handle,
                                           feature_set *set) {
    (void)handle;
    if (set == NULL) return WIFI_ERROR_INVALID_ARGS;
    *set = WIFI_FEATURE_INFRA | WIFI_FEATURE_INFRA_5G | WIFI_FEATURE_P2P;
    return WIFI_SUCCESS;
}

static wifi_error bridge_get_supported_iface_name(wifi_handle handle,
                                                   u32 iface_type,
                                                   char *name, size_t len) {
    const char *selected;
    (void)handle;
    if (name == NULL || len == 0) return WIFI_ERROR_INVALID_ARGS;

    switch ((wifi_interface_type)iface_type) {
        case WIFI_INTERFACE_TYPE_STA:
            selected = "wlan0";
            break;
        case WIFI_INTERFACE_TYPE_P2P:
            selected = "p2p0";
            break;
        case WIFI_INTERFACE_TYPE_AP:
            selected = "wlan1";
            break;
        default:
            return WIFI_ERROR_NOT_SUPPORTED;
    }
    if (strlen(selected) + 1 > len) return WIFI_ERROR_INVALID_ARGS;
    memcpy(name, selected, strlen(selected) + 1);
    return WIFI_SUCCESS;
}

__attribute__((visibility("default")))
wifi_error init_wifi_vendor_hal_func_table(wifi_hal_fn *fn) {
    if (fn == NULL) return WIFI_ERROR_INVALID_ARGS;
    fn->wifi_initialize = bridge_initialize;
    fn->wifi_wait_for_driver_ready = bridge_wait_for_driver_ready;
    fn->wifi_cleanup = bridge_cleanup;
    fn->wifi_event_loop = bridge_event_loop;
    fn->wifi_get_ifaces = bridge_get_ifaces;
    fn->wifi_get_iface_name = bridge_get_iface_name;
    fn->wifi_get_supported_feature_set = bridge_get_features;
    fn->wifi_get_chip_feature_set = bridge_get_chip_features;
    fn->wifi_get_supported_iface_name = bridge_get_supported_iface_name;
    return WIFI_SUCCESS;
}

    ifdef           diosh_config
    __config        _CONFIG1, _HS_OSC & _WDTE_OFF & _PWRTE_OFF & _MCLRE_ON & _CP_OFF & _CPD_OFF & _BOREN_ON & _IESO_OFF & _LVP_OFF & _DEBUG_OFF
    endif           ; diosh_config

    ifdef           diosh_udata
    counter_udata   0, 1, COUNTER_EVENT
    endif           ; diosh_udata

    ifdef           diosh_init
    movlw           0
    banksel         PORTA
    movwf           PORTA
    movlw           ~1
    banksel         TRISA
    movwf           TRISA

    counter_set     0, 100
    endif           ; diosh_init

    ifdef           diosh_idle
    counter_dec     0, 1
    endif           ; diosh_idle

    ifdef           diosh_event_IDLE_QUEUE_COUNTER_EVENT
    movlw           1
    banksel         PORTA
    xorwf           PORTA, F

    pagesel         even
    andwf           PORTA, W
    btfsc           STATUS, Z
    goto            even

    counter_set     0, 42
    pagesel         end_flip
    goto            end_flip

even:
    counter_set     0, 2*42
end_flip:
    endif           ; diosh_event_IDLE_QUEUE_COUNTER_EVENT

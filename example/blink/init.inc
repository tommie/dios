    ifdef       diosh_config
    __config    _CONFIG1, _HS_OSC & _WDTE_OFF & _PWRTE_OFF & _MCLRE_ON & _CP_OFF & _CPD_OFF & _BOREN_ON & _IESO_OFF & _LVP_OFF & _DEBUG_OFF
    endif       ; diosh_config


    ifdef   diosh_init
    movlw   option_init
    banksel OPTION_REG
    movwf   OPTION_REG

    ;; In a larger program, these would be handled by
    ;; a separate port driver module.
    movlw   porta_init
    banksel PORTA
    movwf   PORTA
    movlw   trisa_init
    banksel TRISA
    movwf   TRISA

    movlw   (intcon_init) | (1 << GIE)
    banksel INTCON
    movwf   INTCON
    endif   ; diosh_init

    ifdef   diosh_event_IDLE_QUEUE_TIMER0
    movlw   1 << 0
    banksel PORTA
    xorwf   PORTA, F
    endif   ; diosh_event_IDLE_QUEUE_TIMER0

    ifdef   diosh_event_IDLE_QUEUE_TIMER1
    movlw   1 << 1
    banksel PORTA
    xorwf   PORTA, F
    endif   ; diosh_event_IDLE_QUEUE_TIMER1

    ifdef   diosh_event_IDLE_QUEUE_TIMER2
    movlw   1 << 2
    banksel PORTA
    xorwf   PORTA, F
    endif   ; diosh_event_IDLE_QUEUE_TIMER2

    ;; If this toggles, your periodicity is too fast for the CPU to
    ;; handle. Either increase the prescaling, or increase the TIMER0_FUZZ
    ;; (which is essentially compensation for the time the Timer0 ISR uses.)
    ifdef   diosh_event_IDLE_QUEUE_TIMER0_BAD_FUZZ_EVENT
    movlw   1 << 3
    banksel PORTA
    xorwf   PORTA, F
    endif   ; diosh_event_IDLE_QUEUE_TIMER0_BAD_FUZZ_EVENT

    ifdef   diosh_defs
TIMER0_FUZZ equ     4
    endif   ; diosh_defs

    ifdef           diosh_udata
    timer0_udata    0, TIMER0
    timer0_udata    1, TIMER1
    timer0_udata    2, TIMER2
    endif           ; diosh_udata

    ifdef           diosh_udata_shr
irqsave_fsr         res 1
    endif           ; diosh_udata_shr

    ifdef           diosh_config
    __config        _CONFIG1, _HS_OSC & _WDTE_OFF & _PWRTE_OFF & _MCLRE_ON & _CP_OFF & _CPD_OFF & _BOREN_ON & _IESO_OFF & _LVP_OFF & _DEBUG_OFF
    endif           ; diosh_config

    ifdef           diosh_init
    banksel         PORTA
    clrf            PORTA
    movlw           ~0x0F
    banksel         TRISA
    movwf           TRISA

    ;; TMR0 without prescaler at Fosc/4.
    movlw           ~((1 << T0CS) | (1 << PSA) | (3 << PS0))
    banksel         OPTION_REG
    movwf           OPTION_REG

    timer0_init     0
    timer0_init     1
    timer0_init     2

    movlw           90
    timer0_startw   0
    movlw           110
    timer0_startw   1
    movlw           120
    timer0_startw   2

    bsf             INTCON, GIE
    endif           ; diosh_init

    ifdef           diosh_irq
    movf            FSR, W
    movwf           irqsave_fsr
    endif           ; diosh_irq

    ifdef           diosph_irq
    movf            irqsave_fsr, W
    movwf           FSR
    endif           ; diosph_irq

    ifdef           diosh_irq_timer0
    timer0_recheck  0, 90
    timer0_recheck  1, 110
    timer0_check    2
    endif           ; diosh_irq_timer0

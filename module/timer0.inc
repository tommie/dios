    ;; Timer0 scheduler.
    ;;
    ;; This allows having multiple independent one-shot and periodic timers
    ;; running off of one hardware timer.
    ;;
    ;; * It adjusts the timer register so a roll-around happens when the next
    ;;   timer needs it.
    ;; * It handles setting and clearing T0IE.
    ;; * Periodic timers can be almost cycle-perfect.
    ;;   There is a 1/256 chance that a delay will be one cycle short (a choice
    ;;   to save data space.)
    ;; * It does not handle configuring the timer, such as prescaler adjustments.
    ;; * Delays, timeouts and the number of timers are compile-time constants.
    ;;
    ;; You need to declare an ISR for timer0:
    ;;
    ;;   ; DiOS Configuration
    ;;   irq    irq_timer0, INTCON, T0IF
    ;;
    ;; Set TIMER0_FUZZ to the number of cycles it takes for the timer0 ISR to
    ;; run. Timers expiring FUZZ cycles in the future are considered expired.
    ;; If TIMER0_FUZZ is too large, timers will seem like they are phase-locked
    ;; with each other. Declare TIMER0_BAD_FUZZ_EVENT to enable a sanity-check
    ;; for help trimming this value.
    ;;
    ;; The module uses FSR while inside the irq_timer0 phase, so (1) make sure
    ;; to save it in the ISR and (2) don't use it yourself in that phase.

                    ifdef   diosh_udata
timer0_exp          res     1
                    endif   ; diosh_udata


                    ifdef   diosh_defs
                    ;; Invoke this in phase udata to instantiate a timer.
                    ;; The index must be an integer, but is otherwise uninterpreted.
timer0_udata        macro   index, event
timer0_ev#v(index)  equ     event
timer0_exp#v(index) res     1
                    endm

                    ;; Invoke this in phase init to initialize the timer,
                    ;; before enabling interrupts. You do not have to use
                    ;; this if you invoke `timer0_startw` in phase init.
timer0_init         macro   index
                    banksel timer0_exp#v(index)
                    clrf    timer0_exp#v(index)
                    endm

                    ;; Starts the timer, setting delay to W cycles, where
                    ;; the delay is at most 127.
                    ;;
                    ;; Value zero means "stopped", so if W is zero, we will
                    ;; wait one cycle less than requested.
                    ;;
                    ;; Must not be called from an IRQ phase.
timer0_startw       macro           index
                    timer0_addnow
                    iorlw           0
                    btfsc           STATUS, Z
                    addlw           -1

                    banksel         timer0_exp#v(index)
                    movwf           timer0_exp#v(index)

                    timer0_schedw_  index, 1
                    endm

                    ;; Stops the timer, telling it to not post an event.
timer0_stop         macro   index
                    banksel timer0_exp#v(index)
                    clrf    timer0_exp#v(index)
                    endm

                    ;; Invoke this in phase diosh_irq_timer0.
                    ;;
                    ;; It checks for expiration and fires the event.
timer0_check        macro           index
                    timer0_recheck  index, 0
                    endm

                    ;; Like timer0_check, but allows restarting the timer.
                    ;;
                    ;; On expiration, if `restart_delay` is in [1, 127],
                    ;; the timer is restarted, otherwise stopped.
                    ;; Note the risk of missing the expiration if set too low.
timer0_recheck      macro       index, restart_delay
                    local       expired
                    local       schedule
                    local       mend

                    ;; if (!exp_index) goto mend
                    pagesel     mend
                    banksel     timer0_exp#v(index)
                    movf        timer0_exp#v(index), W
                    btfsc       STATUS, Z
                    goto        mend

                    ;; if ((int8_t) (exp - exp_index) >= 0) goto expired
                    pagesel     expired
                    banksel     timer0_exp
                    subwf       timer0_exp, W
                    addlw       0x80
                    btfss       STATUS, C
                    goto        expired
                    addlw       0x80

                    ;; if ((int8_t) (exp - (exp_index - FUZZ)) < 0) goto schedule
                    ;; Checking the fuzz-corrected value separately to avoid seeing double-overflows.
                    pagesel     schedule
                    addlw       TIMER0_FUZZ
                    addlw       0x80
                    btfsc       STATUS, C
                    goto        schedule

expired:
                    diospost    timer0_ev#v(index)

                    if          restart_delay > 127
                    error       "Assertion failed: restart_delay <= 127"
                    endif
                    banksel     timer0_exp#v(index)
                    if          restart_delay <= 0
                    clrf        timer0_exp#v(index)
                    pagesel     mend
                    goto        mend
                    else

                    movlw       restart_delay
                    addwf       timer0_exp#v(index), W
                    btfsc       STATUS, Z
                    addlw       -1
                    movwf       timer0_exp#v(index)
                    endif       ; restart_delay <= 0

schedule:
                    banksel         timer0_exp#v(index)
                    movf            timer0_exp#v(index), W
                    timer0_schedw_  index, 0
mend:
                    endm

                    ;; Internal macro.
                    ;;
                    ;; W is the expiration time.
timer0_schedw_      macro   index, sync
                    local   mend

                    ;; W = INDF - arg_w
                    ;banksel INDF
                    subwf   INDF, W

                    ;; if (T0IE && (int8_t) (INDF - arg_w) < 0) goto mend
                    pagesel mend
                    addlw   0x80
                    bsf     STATUS, Z
                    btfss   STATUS, C
                    bcf     STATUS, Z
                    ;banksel INTCON
                    btfss   INTCON, T0IE
                    bcf     STATUS, Z
                    btfsc   STATUS, Z
                    goto    mend

                    addlw   0x80                ; Undo the add used for sign-checking. Uses an 8-bit ROT-0x100 cipher.

                    ;; FSR = &exp_index
                    movlw   LOW timer0_exp#v(index)
                    ;banksel FSR
                    movwf   FSR
                    if      (HIGH timer0_exp#v(index)) <= 0xFF
                    bcf     STATUS, IRP
                    else
                    bsf     STATUS, IRP
                    endif

                    ; Changing TMR0 and timer0_exp must be atomic.
                    if      sync
                    ;banksel INTCON
                    bcf     INTCON, GIE
                    timer0_commit_ ; Uses the old value of T0IE.
                    bsf     INTCON, GIE
                    endif   ; sync

                    ;banksel INTCON
                    bsf     INTCON, T0IE
mend:
                    endm

                    ;; Internal macro.
timer0_commit_      macro
                    ifdef       TIMER0_BAD_FUZZ_EVENT
                    local       not_missed
                    endif

                    ;; W = INDF - exp
                    banksel     timer0_exp
                    movf        timer0_exp, W
                    ;banksel     INDF
                    subwf       INDF, W

                    ;; exp = INDF
                    addwf       timer0_exp, F

                    ;; If this is the first timer, then timer0_exp was
                    ;; the previous exp, so we want
                    ;;   TMR = -(INDF - TMR - exp) = TMR - W
                    ;; Else, then timer0_exp was the next exp, so we want
                    ;;   TMR -= W
                    xorlw   0xFF
                    addlw   1

                    ;; TMR0 += W + 2
                    addlw       2 ; Compensate for TMR0 stopping for two cycles after write.
                    banksel     TMR0
                    addwf       TMR0, F

                    ifdef       TIMER0_BAD_FUZZ_EVENT
                    pagesel     not_missed
                    btfss       STATUS, C
                    goto        not_missed

                    ;; If TMR0 wrapped, that means we missed our deadline. I.e.
                    ;; the next expiration was too close in time. We cannot
                    ;; make guarantees about the next expiration(s), and there
                    ;; is no attempt to "catch up." The caller needs to
                    ;; increase TIMER0_FUZZ.
                    diospost    TIMER0_BAD_FUZZ_EVENT
not_missed:
                    endif   ; TIMER0_BAD_FUZZ_EVENT
                    endm

                    ;; Adds the current time to W, useful to compute
                    ;; the expiration for `timer0_startw`.
                    ;;
                    ;; Must not be called from an IRQ phase.
timer0_addnow       macro
                    ;banksel INTCON
                    bcf     INTCON, GIE

                    ;; If !T0IE, then timer0_exp is the previous exp, so W += timer0_exp + TMR0
                    ;; If T0IE, then timer0_exp is the next exp, so W += timer0_exp - -TMR0
                    banksel timer0_exp
                    addwf   timer0_exp, W

                    ;banksel INTCON
                    banksel TMR0
                    addwf   TMR0, W

                    ;banksel INTCON
                    bsf     INTCON, GIE
                    endm
                    endif   ; diosh_defs


                    ifdef   diosh_irq_timer0
                    ifndef  TIMER0_FUZZ
                    error   "TIMER0_FUZZ must be defined"
                    endif


                    ;; timer0_check calls will re-enable the interrupt if appropriate.
                    ;; A cleared T0IE means timer0_exp is the current time, not in the future.
                    ;banksel INTCON
                    bcf     INTCON, T0IE
                    endif   ; diosh_irq_timer0


                    ifdef   diosph_irq_timer0
                    timer0_commit_
                    endif   ; diosph_irq_timer0


                    ifdef   diosh_init
                    banksel timer0_exp
                    clrf    timer0_exp
                    endif   ; diosh_init

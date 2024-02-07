    ;; Event counter.
    ;;
    ;; Provides an API to set, reset and decrement a counter by constants.
    ;; If a set counter reaches zero, an event is posted.
    ;;
    ;;   * Supports counters of any byte-aligned size.
    ;;
    ;; This can be used to create software timers that are, through
	;; some means, periodically decremented. They are equivalent to counting
    ;; up and comparing to expiration values, but can be more efficient since
    ;; the update and the comparison can be the same instruction.

                    ifdef   diosh_udata
counter_udata       macro   index, size, event
                    if      size < 1
                    error   "Assertion failed: size >= 1"
                    endif
counter_n#v(index)  res     size
counter_sz#v(index) equ     size
counter_ev#v(index) equ     event
                    endm
                    endif   ; diosh_udata


                    ifdef   diosh_defs
                    ;; Invoke this before attempting to decrement the counter.
counter_init        macro           index
                    counter_reset   (index)
                    endm

                    ;; Arms the counter and sets its value to n.
                    ;; If this is invoked before `counter_dec`, there is no
                    ;; need for `counter_init`.
counter_set         macro   index, n
                    local   i

                    if  (n) == 0
                    error   "Assertion failed: n > 0"
                    endif

i                   set     0
                    while   i < counter_sz#v(index)
                    banksel counter_n#v(index) + i
                    if      LOW ((n) >> (8*i)) == 0
                    clrf    counter_n#v(index) + i
                    else
                    movlw   LOW ((n) >> (8*i))
                    movwf   counter_n#v(index) + i
                    endif   ; n>>i == 0
i                   set     i + 1
                    endw
                    endm

                    ;; Arms the counter and sets its value to W.
                    ;; If this is invoked before `counter_dec`, there is no
                    ;; need for `counter_init`.
counter_setw        macro   index
                    local   i

                    banksel counter_n#v(index)
                    movwf   counter_n#v(index)

i                   set     1
                    while   i < counter_sz#v(index)
                    banksel counter_n#v(index) + i
                    clrf    counter_n#v(index) + i
i                   set     i + 1
                    endw
                    endm

                    ;; Disarms the counter, disabling events.
counter_reset       macro   index
                    local   i

i                   set     0
                    while   i < counter_sz#v(index)
                    banksel counter_n#v(index) + i
                    clrf    counter_n#v(index) + i
i                   set     i + 1
                    endw
                    endm

                    ;; Decrements the counter by `n` units. If the counter
	                ;; turns negative, it's reset to zero. Eitherway, if
	                ;; the counter reaches zero, an event is posted.
counter_dec         macro       index, n
                    if          (n) > 1
                    local       negative
                    endif
                    local       mend

                    if (n) == 0
                    error   "Assertion failed: n > 0"
                    endif

                    ;; if (!n_index) goto mend
                    pagesel     mend
                    banksel     counter_n#v(index)
                    movf        counter_n#v(index), F
                    btfsc       STATUS, Z
                    goto        mend

                    ;; n_index -= n
                    if          (n) > 1 || counter_sz#v(index) > 1
                    pagesel     negative
i                   set         counter_sz#v(index) - 1
                    while       i >= 0

                    movlw       LOW ((n) >> (8*i))
                    subwf       counter_n#v(index) + i, F

                    movlw       -1
j                   set         i + 2
                    while       j < counter_sz#v(index)
j                   set         j + 1
                    btfss       STATUS, C
                    addwf       counter_n#v(index) + j, F
                    endw

                    if          (n) > 1
                    btfss       STATUS, C
                    goto        negative
                    endif

i                   set         i - 1
                    endw

                    ;; if (n_index != 0) goto mend
                    clrw
                    pagesel     mend
i                   set         0
                    while       i < counter_sz#v(index)
                    banksel     counter_n#v(index) + i
                    iorwf       counter_n#v(index) + i, W
i                   set         i + 1
                    endw

                    btfss       STATUS, Z
                    goto        mend

                    ;; We run reset even when zero, which is a bit wasteful,
                    ;; but simpler. n_index can't be negative if n == 1, though.
                    if          (n) > 1
negative:
                    counter_reset   index
                    endif           ; n > 1
                    else
                    decfsz          counter_n#v(index), F
                    goto            mend
                    endif           ; n > 1 || sz_index > 1

                    diospost        counter_ev#v(index)
mend:
                    endm
                    endif   ; diosh_defs

# 066 External torque PD zero hold

L2-approved bounded zero-hold experiment on frozen065 v2/USD assumptions. Native drive kp/kd remain zero. Fixed observed047 gains drive external P+D using consecutive measured positions and native engine time; native gravity FF + P + D is clamped once to original caps. API qd is observed separately. Root independently reconstructs all terms and applies unchanged physical criteria plus all-state FD speed <=1deg/s.

Entry: launch.ps1 -Role test; prepare/run each installation_audit, provider_diagnosis, provider_connection once. Progress reads the journal only and is never acceptance. Full acceptance requires243records/241states/2native seconds/9artifacts. No actual motor/CAN, calibration, flashing, installation, reboot, training. Revised067 URDF is not imported in this experiment. Old047 multi-pose failure remains unresolved. Result: outputs/isaac-controller-baseline-v1/HANDOFF.md.

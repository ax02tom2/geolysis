# USACE 2025 Appendix C-6b DMT settlement benchmark

Verification date: 2026-11-12

## Reference

U.S. Army Corps of Engineers, EM 1110-1-1905, *Geotechnical Design of Shallow Foundations on Soils*, 31 July 2025:

- Table C-6a: DMT constrained modulus and layer depths, printed pages 369–370.
- Table C-6b: settlement solution for an isolated 8 ft × 8 ft footing on mixed soils, printed pages 371–373.
- Table 7-4 and Eq. 7-10: incremental constrained-modulus settlement procedure.

Official publication record: https://www.publications.usace.army.mil/USACE-Publications/Engineer-Manuals/

## Independent reproduction

The repository benchmark test_usace_2025_appendix_c6b_dmt_mixed_soil_profile transcribes the 46 layer rows from Table C-6a/C-6b and independently calculates each settlement increment using:

\[
\delta_i = \frac{I_{\sigma,i}(q-\sigma'_{zD})}{M_{DMT,i}}H_i
\]

The conversion from feet to inches is applied after calculating each layer increment. The test then sums all 46 independently calculated increments and compares the result with the engine output.

Inputs reproduced from the example:

- Footing: 8 ft × 8 ft isolated spread footing.
- Gross bearing pressure: 2.53 tsf.
- Initial effective stress at footing base: 0.15 tsf.
- Net pressure increment: 2.38 tsf.
- All 46 layer thicknesses, DMT constrained moduli and influence factors are taken from the table.

## Discrepancy recorded

The sum of the 46 tabulated layer settlement increments is approximately **0.827 in**. However, the printed total at the bottom of Table C-6b reads **0.081 inches**.

This is an apparent factor-of-ten inconsistency between the table's individual rows and its printed total. The repository benchmark therefore:

1. Uses the 46 row values and the stated Eq. 7-10 to independently reproduce the sum.
2. Expects approximately 0.827 in from the row-by-row calculation.
3. Does not alter or silently rewrite the published USACE manual value.
4. Records the discrepancy so reviewers can distinguish a source-document arithmetic/typographical issue from a software calculation error.

The value 0.827 in is a reproduction of the listed row calculations, not a claim that USACE has issued a formal erratum.

## Engineering interpretation and limits

- The example is a benchmark for the DMT incremental constrained-modulus method, not a general validation of all DMT interpretation or site characterization.
- Table 7-4 treats 2B as a minimum depth for the isolated footing; the profile must extend farther if induced vertical stress remains material.
- The code must not extrapolate unmeasured DMT modulus below the supplied profile.
- The input DMT constrained modulus must already be interpreted/corrected consistently with the test procedure.
- The engineer remains responsible for verifying site-specific stratigraphy, groundwater, stress influence factors, footing loads and settlement acceptance criteria.

<xsl:stylesheet
        version="2.0"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:tei="http://www.tei-c.org/ns/1.0"
        xpath-default-namespace="http://www.tei-c.org/ns/1.0">
    <xsl:import href="../../../../doc_curation/tei_xsl/markdown/tei-to-markdown.xsl"/>
    <xsl:strip-space elements="seg"/>
    <xsl:template match="rdg">
        <xsl:text>+++(ALT- </xsl:text>
        <xsl:apply-templates/>
        <xsl:text>)+++ </xsl:text>
    </xsl:template>
    <xsl:template match="ref">
        <xsl:text>**</xsl:text>
        <xsl:apply-templates/>
        <xsl:text>**</xsl:text>
    </xsl:template>
    <xsl:template match="seg[@type='pāda']">
        <xsl:apply-templates/>
        <xsl:text>  </xsl:text>
        <xsl:call-template name="newline"/>
    </xsl:template>

</xsl:stylesheet>

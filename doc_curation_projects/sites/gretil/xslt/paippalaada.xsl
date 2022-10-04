<xsl:stylesheet
        version="2.0"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:tei="http://www.tei-c.org/ns/1.0"
        xpath-default-namespace="http://www.tei-c.org/ns/1.0">

    <xsl:import href="tei-to-markdown-gretil.xsl"/>
    <xsl:template match="head">
        <xsl:call-template name="newline"/>
        <xsl:text>## </xsl:text>
        <xsl:apply-templates/>
        <xsl:call-template name="newline"/>
    </xsl:template>
    <xsl:template match="div[@type='hymn']">
        <xsl:call-template name="newline"/>
        <xsl:text>### </xsl:text>
        <xsl:value-of select="@n"/>
        <xsl:call-template name="newline"/>
        <xsl:apply-templates/>
    </xsl:template>
    <xsl:template match="lg">
        <xsl:call-template name="newline"/>
        <xsl:text>#### </xsl:text>
        <xsl:value-of select="@xml:id"/>
        <xsl:call-template name="newline"/>
        <xsl:apply-templates/>
    </xsl:template>

</xsl:stylesheet>
